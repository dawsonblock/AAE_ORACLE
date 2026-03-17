import Foundation

public struct PreparedLoopAction: Sendable {
    public let resolution: SkillResolution
    public let policyDecision: PolicyDecision

    public init(resolution: SkillResolution, policyDecision: PolicyDecision) {
        self.resolution = resolution
        self.policyDecision = policyDecision
    }
}

public struct LoopExecutionResult: Sendable {
    public let toolResult: ToolResult
    public let actionResult: ActionResult
    public let intent: ActionIntent
    public let selectedCandidate: ElementCandidate?
    public let approvalPending: Bool
    public let budgetTerminationReason: LoopTerminationReason?

    public init(
        toolResult: ToolResult,
        actionResult: ActionResult,
        intent: ActionIntent,
        selectedCandidate: ElementCandidate?,
        approvalPending: Bool,
        budgetTerminationReason: LoopTerminationReason?
    ) {
        self.toolResult = toolResult
        self.actionResult = actionResult
        self.intent = intent
        self.selectedCandidate = selectedCandidate
        self.approvalPending = approvalPending
        self.budgetTerminationReason = budgetTerminationReason
    }
}

@MainActor
public final class ExecutionCoordinator {
    private let executionDriver: any AgentExecutionDriver
    private let skillRegistry: SkillRegistry
    private let policyEngine: PolicyEngine
    private let memoryStore: UnifiedMemoryStore

    public init(
        executionDriver: any AgentExecutionDriver,
        skillRegistry: SkillRegistry = .live(),
        policyEngine: PolicyEngine = PolicyEngine(),
        memoryStore: UnifiedMemoryStore = UnifiedMemoryStore()
    ) {
        self.executionDriver = executionDriver
        self.skillRegistry = skillRegistry
        self.policyEngine = policyEngine
        self.memoryStore = memoryStore
    }

    public func prepare(
        decision: PlannerDecision,
        stateBundle: LoopStateBundle,
        surface: RuntimeSurface = .recipe,
        toolName: String = "agent_loop"
    ) throws -> PreparedLoopAction {
        let resolution = try prepareAction(
            decision: decision,
            state: stateBundle.worldState,
            taskContext: stateBundle.taskContext
        )
        return prepare(
            resolution: resolution,
            surface: surface,
            toolName: toolName
        )
    }

    public func prepare(
        resolution: SkillResolution,
        surface: RuntimeSurface = .recipe,
        toolName: String = "agent_loop"
    ) -> PreparedLoopAction {
        let policyDecision = policyEngine.evaluate(
            intent: resolution.intent,
            context: PolicyEvaluationContext(
                surface: surface,
                toolName: toolName,
                appName: resolution.intent.app,
                agentKind: resolution.intent.agentKind,
                workspaceRoot: resolution.intent.workspaceRoot,
                workspaceRelativePath: resolution.intent.workspaceRelativePath,
                commandCategory: resolution.intent.commandCategory
            )
        )
        return PreparedLoopAction(resolution: resolution, policyDecision: policyDecision)
    }

    public func prepare(
        intent: ActionIntent,
        selectedCandidate: ElementCandidate? = nil,
        semanticQuery: ElementQuery? = nil,
        repositorySnapshotID: String? = nil,
        surface: RuntimeSurface = .recipe,
        toolName: String = "agent_loop"
    ) -> PreparedLoopAction {
        prepare(
            resolution: SkillResolution(
                intent: intent,
                selectedCandidate: selectedCandidate,
                semanticQuery: semanticQuery,
                repositorySnapshotID: repositorySnapshotID
            ),
            surface: surface,
            toolName: toolName
        )
    }

    public func terminationReason(
        for preparedAction: PreparedLoopAction
    ) -> LoopTerminationReason? {
        if preparedAction.policyDecision.requiresApproval {
            return .approvalTimeout
        }
        if preparedAction.policyDecision.blockedByPolicy {
            return .policyBlocked
        }
        return nil
    }

    public func execute(
        preparedAction: PreparedLoopAction,
        decision: PlannerDecision,
        budgetState: inout LoopBudgetState,
        budget: LoopBudget
    ) -> LoopExecutionResult {
        let toolResult = executionDriver.execute(
            intent: preparedAction.resolution.intent,
            plannerDecision: decision,
            selectedCandidate: preparedAction.resolution.selectedCandidate
        )
        let budgetReason = budgetState.registerExecution(
            intent: preparedAction.resolution.intent,
            budget: budget
        )
        let actionResult = ActionResult.from(dict: toolResult.data?["action_result"] as? [String: Any] ?? [:])
            ?? ActionResult(
                success: toolResult.success,
                verified: toolResult.success,
                message: toolResult.error
            )
        return LoopExecutionResult(
            toolResult: toolResult,
            actionResult: actionResult,
            intent: preparedAction.resolution.intent,
            selectedCandidate: preparedAction.resolution.selectedCandidate,
            approvalPending: actionResult.approvalStatus == ApprovalStatus.pending.rawValue,
            budgetTerminationReason: budgetReason
        )
    }

    private func prepareAction(
        decision: PlannerDecision,
        state: WorldState,
        taskContext: TaskContext
    ) throws -> SkillResolution {
        if decision.agentKind == .code {
            // Phase 3: Build effective task context with AAE path hints
            var effectiveTaskContext = taskContext.with(
                plannerPreferredPath: decision.actionContract.workspaceRelativePath
            )
            
            // If we have AAE candidate info with target file, propagate it
            if let aaeCandidateID = taskContext.aaeCandidateID,
               taskContext.candidateSource == .aaeAdvised || taskContext.candidateSource == .oracleAAEHybrid {
                effectiveTaskContext = effectiveTaskContext.withTargetPathHints(
                    targetFile: taskContext.targetFile,
                    rankedFallbackPaths: taskContext.rankedFallbackPaths,
                    dominantLanguage: taskContext.dominantLanguage,
                    patchFileCountLimit: taskContext.patchFileCountLimit
                )
            }
            
            guard let codeSkill = skillRegistry.getCode(decision.skillName) else {
                throw CodeSkillResolutionError.noRelevantFiles(decision.skillName)
            }
            return try codeSkill.resolve(
                taskContext: effectiveTaskContext,
                state: state,
                memoryStore: memoryStore
            )
        }

        if decision.actionContract.skillName == "focus" {
            let app = decision.actionContract.targetLabel ?? state.observation.app ?? "unknown"
            let intent = ActionIntent.focus(app: app)
            return SkillResolution(intent: intent)
        }

        if let skill = skillRegistry.get(decision.skillName) {
            let query = decision.semanticQuery ?? ElementQuery(
                text: decision.actionContract.targetLabel,
                role: decision.actionContract.targetRole,
                editable: decision.skillName == "type" || decision.skillName == "fill_form",
                clickable: decision.skillName == "click" || decision.skillName == "read_file",
                visibleOnly: true,
                app: state.observation.app
            )
            return try skill.resolve(
                query: query,
                state: state,
                memoryStore: memoryStore
            )
        }

        let intent = ActionIntent(
            agentKind: decision.agentKind,
            app: state.observation.app ?? decision.actionContract.targetLabel ?? "unknown",
            name: decision.actionContract.skillName,
            action: decision.actionContract.skillName,
            query: decision.actionContract.targetLabel,
            role: decision.actionContract.targetRole,
            workspaceRelativePath: decision.actionContract.workspaceRelativePath
        )
        return SkillResolution(intent: intent, semanticQuery: decision.semanticQuery)
    }
}
