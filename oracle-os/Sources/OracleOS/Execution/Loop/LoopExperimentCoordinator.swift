import Foundation

@MainActor
public final class LoopExperimentCoordinator {
    private let experimentManager: ExperimentManager
    private let executionCoordinator: ExecutionCoordinator
    private let observationProvider: any ObservationProvider
    private let stateAbstraction: StateAbstraction
    private let recoveryEngine: RecoveryEngine
private let memoryStore: UnifiedMemoryStore
    private let projectMemoryCoordinator: LoopProjectMemoryCoordinator
    private let repositoryIndexer: RepositoryIndexer

    public init(
        experimentManager: ExperimentManager,
        executionCoordinator: ExecutionCoordinator,
        observationProvider: any ObservationProvider,
        stateAbstraction: StateAbstraction,
        recoveryEngine: RecoveryEngine,
memoryStore: UnifiedMemoryStore,
        repositoryIndexer: RepositoryIndexer,
        projectMemoryCoordinator: LoopProjectMemoryCoordinator
    ) {
        self.experimentManager = experimentManager
        self.executionCoordinator = executionCoordinator
        self.observationProvider = observationProvider
        self.stateAbstraction = stateAbstraction
        self.recoveryEngine = recoveryEngine
        self.memoryStore = memoryStore
        self.repositoryIndexer = repositoryIndexer
        self.projectMemoryCoordinator = projectMemoryCoordinator
    }

    public func handle(
        decision: PlannerDecision,
        experimentSpec: ExperimentSpec,
        taskContext: TaskContext,
        worldState: WorldState,
        budgetState: inout LoopBudgetState,
        step: Int,
        budget: LoopBudget,
        diagnostics: inout LoopDiagnostics
    ) async -> LoopOutcome? {
        do {
            let results = try await experimentManager.run(
                spec: experimentSpec,
                architectureRiskScore: decision.architectureFindings.map(\.riskScore).max() ?? 0
            )
            guard let selected = experimentManager.replaySelected(from: results) else {
                projectMemoryCoordinator.recordRejectedApproach(
                    title: "Experiment fanout produced no viable winner",
                    taskContext: taskContext,
                    decision: decision,
                    body: results.map { "\($0.candidate.title): \($0.commandResults.map(\.succeeded).allSatisfy { $0 })" }.joined(separator: "\n")
                )
                diagnostics.append(
                    LoopStepSummary(
                        stepIndex: step,
                        source: decision.source,
                        skillName: decision.skillName,
                        experimentID: experimentSpec.id,
                        success: false,
                        failure: .patchApplyFailed,
                        notes: decision.notes + ["no experiment candidate passed ranking"]
                    )
                )
                return LoopOutcome(
                    reason: .lowConfidenceRepeatedFailure,
                    finalWorldState: worldState,
                    steps: step + 1,
                    recoveries: budgetState.recoveries,
                    lastFailure: .patchApplyFailed,
                    diagnostics: diagnostics
                )
            }

            let replayCommand = CommandSpec(
                category: .generatePatch,
                executable: "/usr/bin/env",
                arguments: [],
                workspaceRoot: experimentSpec.workspaceRoot,
                workspaceRelativePath: selected.workspaceRelativePath,
                summary: "replay experiment candidate \(selected.title)"
            )
            let replayIntent = ActionIntent.code(
                name: "Replay experiment candidate",
                command: replayCommand,
                workspaceRelativePath: selected.workspaceRelativePath,
                text: selected.content
            )
            let replayContract = ActionContract(
                id: [
                    "code",
                    "experiment-replay",
                    selected.workspaceRelativePath,
                    experimentSpec.id,
                    selected.id,
                ].joined(separator: "|"),
                agentKind: .code,
                skillName: "generate_patch",
                targetRole: nil,
                targetLabel: selected.title,
                locatorStrategy: "experiment-replay",
                workspaceRelativePath: selected.workspaceRelativePath,
                commandCategory: CodeCommandCategory.generatePatch.rawValue,
                plannerFamily: PlannerFamily.code.rawValue
            )
            let selectedResult = results.first(where: { $0.candidate.id == selected.id })
            let replayDecision = PlannerDecision(
                agentKind: .code,
                skillName: "generate_patch",
                plannerFamily: .code,
                stepPhase: .engineering,
                actionContract: replayContract,
                source: .exploration,
                fallbackReason: decision.fallbackReason,
                projectMemoryRefs: decision.projectMemoryRefs,
                architectureFindings: selectedResult?.architectureFindings ?? decision.architectureFindings,
                refactorProposalID: selectedResult?.refactorProposalID ?? decision.refactorProposalID,
                experimentSpec: experimentSpec,
                experimentCandidateID: selected.id,
                experimentSandboxPath: selectedResult?.sandboxPath,
                selectedExperimentCandidate: true,
                experimentOutcome: selectedResult?.succeeded == true ? "selected-replay" : "selected-with-failures",
                knowledgeTier: .candidate,
                notes: decision.notes + ["replaying selected experiment candidate"]
            )

            let preparedReplay = executionCoordinator.prepare(
                intent: replayIntent,
                surface: .recipe,
                toolName: "agent_loop_experiment"
            )
            if let policyTermination = executionCoordinator.terminationReason(for: preparedReplay) {
                diagnostics.append(
                    LoopStepSummary(
                        stepIndex: step,
                        source: replayDecision.source,
                        skillName: replayDecision.skillName,
                        experimentID: experimentSpec.id,
                        success: false,
                        preparationOutcome: .ready,
                        policyOutcome: .blocked,
                        executionOutcome: .skipped,
                        terminationReason: policyTermination,
                        notes: replayDecision.notes + [
                            policyTermination == .approvalTimeout
                                ? "approval required before experiment replay"
                                : "policy precheck blocked experiment replay"
                        ]
                    )
                )
                return LoopOutcome(
                    reason: policyTermination,
                    finalWorldState: worldState,
                    steps: step + 1,
                    recoveries: budgetState.recoveries,
                    lastFailure: nil,
                    diagnostics: diagnostics
                )
            }

            let execution = executionCoordinator.execute(
                preparedAction: preparedReplay,
                decision: replayDecision,
                budgetState: &budgetState,
                budget: budget
            )
            let actionResult = execution.actionResult

            diagnostics.append(
                LoopStepSummary(
                    stepIndex: step,
                    source: replayDecision.source,
                    skillName: replayDecision.skillName,
                    experimentID: experimentSpec.id,
                    success: actionResult.success,
                    failure: actionResult.failureClass.flatMap(FailureClass.init(rawValue:)),
                    notes: replayDecision.notes
                )
            )

            if let budgetReason = execution.budgetTerminationReason {
                return LoopOutcome(
                    reason: budgetReason,
                    finalWorldState: worldState,
                    steps: step + 1,
                    recoveries: budgetState.recoveries,
                    lastFailure: .patchApplyFailed,
                    diagnostics: diagnostics
                )
            }

            if execution.approvalPending {
                return LoopOutcome(
                    reason: .approvalTimeout,
                    finalWorldState: worldState,
                    steps: step + 1,
                    recoveries: budgetState.recoveries,
                    lastFailure: .patchApplyFailed,
                    diagnostics: diagnostics
                )
            }

            if actionResult.success {
                projectMemoryCoordinator.recordArchitectureDecision(
                    decision: replayDecision,
                    taskContext: taskContext
                )
                return nil
            }

            if budgetState.canRecover(under: budget) {
                let afterObservation = observationProvider.observe()
                let afterWorldState = WorldState(
                    observation: afterObservation,
                    lastAction: execution.intent,
                    repositorySnapshot: repositorySnapshot(for: taskContext),
                    stateAbstraction: stateAbstraction
                )
                let recoveryAttempt = await recoveryEngine.recover(
                    failure: .patchApplyFailed,
                    state: afterWorldState,
                    memoryStore: memoryStore
                )
                budgetState.registerRecoveryAttempt()
                var recordedFailure = false
                if let preparation = recoveryAttempt.preparation {
                    let recoveryDecision = PlannerDecision(
                        agentKind: preparation.resolution.intent.agentKind,
                        skillName: preparation.strategyName,
                        plannerFamily: .code,
                        stepPhase: .engineering,
                        actionContract: ActionContract.from(
                            intent: preparation.resolution.intent,
                            method: preparation.resolution.semanticQuery == nil ? "recovery" : "recovery-query",
                            selectedElementLabel: preparation.resolution.selectedCandidate?.element.label,
                            plannerFamily: PlannerFamily.code.rawValue
                        ),
                        source: .recovery,
                        fallbackReason: decision.fallbackReason,
                        projectMemoryRefs: decision.projectMemoryRefs,
                        architectureFindings: decision.architectureFindings,
                        refactorProposalID: decision.refactorProposalID,
                        experimentSpec: experimentSpec,
                        knowledgeTier: .recovery,
                        notes: ["experiment replay recovery"],
                        recoveryTagged: true,
                        recoveryStrategy: preparation.strategyName,
                        recoverySource: FailureClass.patchApplyFailed.rawValue
                    )
                    let preparedRecovery = executionCoordinator.prepare(
                        resolution: preparation.resolution,
                        surface: .recipe,
                        toolName: "agent_loop_experiment_recovery"
                    )
                    if let policyTermination = executionCoordinator.terminationReason(for: preparedRecovery) {
                        diagnostics.recordRecovery(
                            stepIndex: step,
                            strategyName: preparation.strategyName,
                            success: false,
                            failure: .patchApplyFailed,
                            notes: preparation.notes + ["experiment replay recovery blocked by policy", policyTermination.rawValue]
                        )
                        return LoopOutcome(
                            reason: policyTermination,
                            finalWorldState: afterWorldState,
                            steps: step + 1,
                            recoveries: budgetState.recoveries,
                            lastFailure: .patchApplyFailed,
                            diagnostics: diagnostics
                        )
                    }

                    let recoveryExecution = executionCoordinator.execute(
                        preparedAction: preparedRecovery,
                        decision: recoveryDecision,
                        budgetState: &budgetState,
                        budget: budget
                    )
                    let recoveryActionResult = recoveryExecution.actionResult
                    memoryStore.recordStrategy(
                        StrategyRecord(
                            app: afterWorldState.observation.app ?? "unknown",
                            strategy: preparation.strategyName,
                            success: recoveryActionResult.success
                        )
                    )

                    if let budgetReason = recoveryExecution.budgetTerminationReason {
                        diagnostics.recordRecovery(
                            stepIndex: step,
                            strategyName: preparation.strategyName,
                            success: false,
                            failure: .patchApplyFailed,
                            notes: preparation.notes + ["experiment replay recovery exceeded budget"]
                        )
                        return LoopOutcome(
                            reason: budgetReason,
                            finalWorldState: afterWorldState,
                            steps: step + 1,
                            recoveries: budgetState.recoveries,
                            lastFailure: .patchApplyFailed,
                            diagnostics: diagnostics
                        )
                    }

                    if recoveryExecution.approvalPending {
                        diagnostics.recordRecovery(
                            stepIndex: step,
                            strategyName: preparation.strategyName,
                            success: false,
                            failure: .patchApplyFailed,
                            notes: preparation.notes + ["experiment replay recovery paused pending approval"]
                        )
                        return LoopOutcome(
                            reason: .approvalTimeout,
                            finalWorldState: afterWorldState,
                            steps: step + 1,
                            recoveries: budgetState.recoveries,
                            lastFailure: .patchApplyFailed,
                            diagnostics: diagnostics
                        )
                    }

                    if recoveryActionResult.success {
                        diagnostics.recordRecovery(
                            stepIndex: step,
                            strategyName: preparation.strategyName,
                            success: true,
                            notes: preparation.notes + ["experiment replay recovery succeeded"]
                        )
                        return nil
                    }

                    recordedFailure = true
                    diagnostics.recordRecovery(
                        stepIndex: step,
                        strategyName: preparation.strategyName,
                        success: false,
                        failure: .patchApplyFailed,
                        notes: preparation.notes + ["experiment replay recovery failed"]
                    )
                }

                if !recordedFailure {
                    memoryStore.recordStrategy(
                        StrategyRecord(
                            app: afterWorldState.observation.app ?? "unknown",
                            strategy: recoveryAttempt.strategyName ?? "none",
                            success: false
                        )
                    )
                    diagnostics.recordRecovery(
                        stepIndex: step,
                        strategyName: recoveryAttempt.strategyName,
                        success: false,
                        failure: .patchApplyFailed,
                        notes: ["experiment replay recovery failed", recoveryAttempt.message]
                    )
                }
            }

            return LoopOutcome(
                reason: .lowConfidenceRepeatedFailure,
                finalWorldState: worldState,
                steps: step + 1,
                recoveries: budgetState.recoveries,
                lastFailure: .patchApplyFailed,
                diagnostics: diagnostics
            )
        } catch {
            projectMemoryCoordinator.recordRejectedApproach(
                title: "Experiment execution failed",
                taskContext: taskContext,
                decision: decision,
                body: error.localizedDescription
            )
            diagnostics.append(
                LoopStepSummary(
                    stepIndex: step,
                    source: decision.source,
                    skillName: decision.skillName,
                    experimentID: experimentSpec.id,
                    success: false,
                    failure: .patchApplyFailed,
                    notes: decision.notes + [error.localizedDescription]
                )
            )
            return LoopOutcome(
                reason: .lowConfidenceRepeatedFailure,
                finalWorldState: worldState,
                steps: step + 1,
                recoveries: budgetState.recoveries,
                lastFailure: .patchApplyFailed,
                diagnostics: diagnostics
            )
        }
    }

    private func repositorySnapshot(for taskContext: TaskContext) -> RepositorySnapshot? {
        guard taskContext.agentKind == .code || taskContext.agentKind == .mixed,
              let workspaceRoot = taskContext.workspaceRoot
        else {
            return nil
        }
        return repositoryIndexer.indexIfNeeded(workspaceRoot: URL(fileURLWithPath: workspaceRoot, isDirectory: true))
    }
}
