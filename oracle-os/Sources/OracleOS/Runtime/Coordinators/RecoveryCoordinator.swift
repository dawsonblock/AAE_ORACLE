import Foundation

@MainActor
public final class RecoveryCoordinator {
    private let observationProvider: any ObservationProvider
    private let stateAbstraction: StateAbstraction
    private let recoveryEngine: RecoveryEngine
    private let executionCoordinator: ExecutionCoordinator
    private let learningCoordinator: LearningCoordinator
    private let repositoryIndexer: RepositoryIndexer
    private let automationHost: AutomationHost
    private let browserPageStateBuilder: BrowserPageStateBuilder

    public init(
        observationProvider: any ObservationProvider,
        stateAbstraction: StateAbstraction = StateAbstraction(),
        recoveryEngine: RecoveryEngine = RecoveryEngine(),
        executionCoordinator: ExecutionCoordinator,
        learningCoordinator: LearningCoordinator,
        repositoryIndexer: RepositoryIndexer = RepositoryIndexer(),
        automationHost: AutomationHost = .live(),
        browserPageStateBuilder: BrowserPageStateBuilder = BrowserPageStateBuilder()
    ) {
        self.observationProvider = observationProvider
        self.stateAbstraction = stateAbstraction
        self.recoveryEngine = recoveryEngine
        self.executionCoordinator = executionCoordinator
        self.learningCoordinator = learningCoordinator
        self.repositoryIndexer = repositoryIndexer
        self.automationHost = automationHost
        self.browserPageStateBuilder = browserPageStateBuilder
    }

    public func recover(
        from failure: FailureClass,
        decision: PlannerDecision,
        stateBundle: LoopStateBundle,
        budget: LoopBudget,
        budgetState: inout LoopBudgetState,
        diagnostics: inout LoopDiagnostics,
        stepIndex: Int,
        failureNote: String,
        successNote: String
    ) async -> LoopTermination {
        guard budgetState.canRecover(under: budget) else {
            diagnostics.recordRecovery(
                stepIndex: stepIndex,
                strategyName: nil,
                success: false,
                failure: failure,
                notes: ["recovery budget exhausted"]
            )
            return .finished(
                LoopOutcome(
                    reason: .unrecoverableFailure,
                    finalWorldState: stateBundle.worldState,
                    steps: stepIndex + 1,
                    recoveries: budgetState.recoveries,
                    lastFailure: failure,
                    diagnostics: diagnostics
                )
            )
        }

        budgetState.registerRecoveryAttempt()
        let recoveryAttempt = await recoveryEngine.recover(
            failure: failure,
            state: stateBundle.worldState,
            memoryStore: learningCoordinator.appMemoryStore
        )

        guard let preparation = recoveryAttempt.preparation else {
            learningCoordinator.recordStrategy(
                app: stateBundle.observation.app ?? "unknown",
                strategy: recoveryAttempt.strategyName ?? "none",
                success: false
            )
            diagnostics.recordRecovery(
                stepIndex: stepIndex,
                strategyName: recoveryAttempt.strategyName,
                success: false,
                failure: failure,
                notes: [failureNote, recoveryAttempt.message]
            )
            return .finished(
                LoopOutcome(
                    reason: .unrecoverableFailure,
                    finalWorldState: stateBundle.worldState,
                    steps: stepIndex + 1,
                    recoveries: budgetState.recoveries,
                    lastFailure: failure,
                    diagnostics: diagnostics
                )
            )
        }

        let recoveryDecision = makeRecoveryDecision(
            from: decision,
            preparation: preparation,
            failure: failure
        )
        let preparedAction = executionCoordinator.prepare(
            resolution: preparation.resolution,
            surface: .recipe,
            toolName: "agent_loop_recovery"
        )
        if let policyTermination = executionCoordinator.terminationReason(for: preparedAction) {
            learningCoordinator.recordStrategy(
                app: stateBundle.observation.app ?? "unknown",
                strategy: preparation.strategyName,
                success: false
            )
            diagnostics.recordPolicy(
                stepIndex: stepIndex,
                outcome: .blocked,
                notes: ["recovery blocked by policy"]
            )
            diagnostics.recordRecovery(
                stepIndex: stepIndex,
                strategyName: preparation.strategyName,
                success: false,
                failure: failure,
                notes: preparation.notes + [failureNote, "recovery blocked by policy"]
            )
            return .finished(
                LoopOutcome(
                    reason: policyTermination,
                    finalWorldState: stateBundle.worldState,
                    steps: stepIndex + 1,
                    recoveries: budgetState.recoveries,
                    lastFailure: failure,
                    diagnostics: diagnostics
                )
            )
        }

        diagnostics.recordPolicy(stepIndex: stepIndex, outcome: .allowed)
        let execution = executionCoordinator.execute(
            preparedAction: preparedAction,
            decision: recoveryDecision,
            budgetState: &budgetState,
            budget: budget
        )
        let actionResult = execution.actionResult
        learningCoordinator.recordStrategy(
            app: stateBundle.observation.app ?? "unknown",
            strategy: preparation.strategyName,
            success: actionResult.success
        )

        if let budgetReason = execution.budgetTerminationReason {
            diagnostics.recordRecovery(
                stepIndex: stepIndex,
                strategyName: preparation.strategyName,
                success: false,
                failure: failure,
                notes: preparation.notes + [failureNote, "recovery execution exceeded budget"]
            )
            return .finished(
                LoopOutcome(
                    reason: budgetReason,
                    finalWorldState: stateBundle.worldState,
                    steps: stepIndex + 1,
                    recoveries: budgetState.recoveries,
                    lastFailure: failure,
                    diagnostics: diagnostics
                )
            )
        }

        if execution.approvalPending {
            diagnostics.recordRecovery(
                stepIndex: stepIndex,
                strategyName: preparation.strategyName,
                success: false,
                failure: failure,
                notes: preparation.notes + [failureNote, "recovery paused pending approval"]
            )
            return .finished(
                LoopOutcome(
                    reason: .approvalTimeout,
                    finalWorldState: stateBundle.worldState,
                    steps: stepIndex + 1,
                    recoveries: budgetState.recoveries,
                    lastFailure: failure,
                    diagnostics: diagnostics
                )
            )
        }

        if actionResult.success {
            // Record the successful recovery in the learning system so that
            // project memory (known-good patterns, architecture decisions) also
            // benefits from recovery discoveries — not just the strategy store.
            learningCoordinator.recordSuccess(
                decision: recoveryDecision,
                intent: preparedAction.resolution.intent,
                taskContext: stateBundle.taskContext
            )
            diagnostics.recordRecovery(
                stepIndex: stepIndex,
                strategyName: preparation.strategyName,
                success: true,
                notes: preparation.notes + [successNote]
            )
            return .continueRunning
        }

        let afterStateBundle = refreshedStateBundle(from: stateBundle, lastAction: execution.intent)
        let recoveryFailure = FailureClassifier.classifyAction(
            intent: execution.intent,
            result: actionResult,
            before: stateBundle.observation,
            after: afterStateBundle.observation,
            selectedCandidate: execution.selectedCandidate,
            ambiguityScore: execution.selectedCandidate?.ambiguityScore
        ) ?? failure

        learningCoordinator.recordFailure(
            failure: recoveryFailure,
            stateBundle: afterStateBundle
        )
        diagnostics.recordRecovery(
            stepIndex: stepIndex,
            strategyName: preparation.strategyName,
            success: false,
            failure: recoveryFailure,
            notes: preparation.notes + [failureNote]
        )
        return .finished(
            LoopOutcome(
                reason: .unrecoverableFailure,
                finalWorldState: afterStateBundle.worldState,
                steps: stepIndex + 1,
                recoveries: budgetState.recoveries,
                lastFailure: recoveryFailure,
                diagnostics: diagnostics
            )
        )
    }

    private func refreshedStateBundle(from stateBundle: LoopStateBundle, lastAction: ActionIntent?) -> LoopStateBundle {
        let observation = observationProvider.observe()
        let repositorySnapshot = repositorySnapshot(for: stateBundle.taskContext)
        let worldState = WorldState(
            observation: observation,
            lastAction: lastAction,
            repositorySnapshot: repositorySnapshot,
            stateAbstraction: stateAbstraction
        )
        return LoopStateBundle(
            taskContext: stateBundle.taskContext,
            observation: observation,
            worldState: worldState,
            repositorySnapshot: repositorySnapshot,
            hostSnapshot: automationHost.snapshots.captureSnapshot(appName: observation.app),
            browserSession: browserPageStateBuilder.build(from: observation),
            memoryContext: MemoryQueryContext(taskContext: stateBundle.taskContext, worldState: worldState)
        )
    }

    private func repositorySnapshot(for taskContext: TaskContext) -> RepositorySnapshot? {
        guard taskContext.agentKind == .code || taskContext.agentKind == .mixed,
              let workspaceRoot = taskContext.workspaceRoot
        else {
            return nil
        }
        return repositoryIndexer.indexIfNeeded(workspaceRoot: URL(fileURLWithPath: workspaceRoot, isDirectory: true))
    }

    private func makeRecoveryDecision(
        from originatingDecision: PlannerDecision,
        preparation: RecoveryPreparation,
        failure: FailureClass
    ) -> PlannerDecision {
        let selectedLabel = preparation.resolution.selectedCandidate?.element.label
        let actionContract = ActionContract.from(
            intent: preparation.resolution.intent,
            method: preparation.resolution.semanticQuery == nil ? "recovery" : "recovery-query",
            selectedElementLabel: selectedLabel,
            plannerFamily: originatingDecision.plannerFamily.rawValue
        )

        return PlannerDecision(
            agentKind: preparation.resolution.intent.agentKind,
            skillName: actionContract.skillName,
            plannerFamily: originatingDecision.plannerFamily,
            stepPhase: originatingDecision.stepPhase,
            actionContract: actionContract,
            source: .recovery,
            workflowID: originatingDecision.workflowID,
            workflowStepID: originatingDecision.workflowStepID,
            fallbackReason: originatingDecision.fallbackReason,
            semanticQuery: preparation.resolution.semanticQuery,
            projectMemoryRefs: originatingDecision.projectMemoryRefs,
            architectureFindings: originatingDecision.architectureFindings,
            refactorProposalID: originatingDecision.refactorProposalID,
            knowledgeTier: .recovery,
            notes: originatingDecision.notes + preparation.notes,
            recoveryTagged: true,
            recoveryStrategy: preparation.strategyName,
            recoverySource: failure.rawValue
        )
    }
}
