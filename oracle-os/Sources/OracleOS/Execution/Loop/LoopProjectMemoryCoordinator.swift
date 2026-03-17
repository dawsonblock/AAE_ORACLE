import Foundation

public struct LoopProjectMemoryCoordinator: @unchecked Sendable {
    private let memoryStore: UnifiedMemoryStore

    public init(memoryStore: UnifiedMemoryStore) {
        self.memoryStore = memoryStore
    }

    public func recordOpenProblem(
        outcome: LoopOutcome,
        taskContext: TaskContext,
        decision: PlannerDecision?
    ) {
        guard taskContext.agentKind == .code || taskContext.agentKind == .mixed else {
            return
        }
        guard outcome.reason != .goalAchieved else {
            return
        }
        if let root = taskContext.workspaceRoot {
            memoryStore.setWorkspaceRoot(root)
        }
        do {
            try memoryStore.recordOpenProblem(
                title: taskContext.goal.description,
                summary: "Loop ended with \(outcome.reason.rawValue)",
                knowledgeClass: .reusable,
                affectedModules: decision?.architectureFindings.flatMap(\.affectedModules) ?? [],
                evidenceRefs: decision?.projectMemoryRefs.map(\.path) ?? [],
                sourceTraceIDs: [],
                body: """
                Reason: \(outcome.reason.rawValue)
                Last failure: \(outcome.lastFailure?.rawValue ?? "none")
                Steps: \(outcome.steps)
                Recoveries: \(outcome.recoveries)
                """
            )
        } catch {
            return
        }
    }

    public func recordArchitectureDecision(
        decision: PlannerDecision,
        taskContext: TaskContext
    ) {
        let majorFindings = decision.architectureFindings.filter {
            $0.severity == .critical || $0.riskScore >= 0.5
        }
        guard !majorFindings.isEmpty,
              let refactorProposalID = decision.refactorProposalID,
              taskContext.agentKind == .code || taskContext.agentKind == .mixed
        else {
            return
        }

        if let root = taskContext.workspaceRoot {
            memoryStore.setWorkspaceRoot(root)
        }
        do {
            try memoryStore.recordArchitectureDecision(
                title: "Architecture review for \(taskContext.goal.description)",
                summary: "High-impact change surfaced \(majorFindings.count) major architecture finding(s).",
                knowledgeClass: .reusable,
                affectedModules: Array(Set(majorFindings.flatMap(\.affectedModules))).sorted(),
                evidenceRefs: decision.projectMemoryRefs.map(\.path),
                sourceTraceIDs: [],
                body: """
                Refactor proposal id: \(refactorProposalID)
                Findings:
                \(majorFindings.map { "- \($0.title): \($0.summary)" }.joined(separator: "\n"))
                """
            )
        } catch {
            return
        }
    }

    public func recordKnownGoodPattern(
        decision: PlannerDecision,
        intent: ActionIntent,
        taskContext: TaskContext
    ) {
        guard intent.agentKind == .code,
              let workspaceRoot = taskContext.workspaceRoot,
              let commandCategory = intent.commandCategory,
              memoryStore.appMemory.commandBias(category: commandCategory, workspaceRoot: workspaceRoot) >= 0.1
        else {
            return
        }

        memoryStore.setWorkspaceRoot(workspaceRoot)
        do {
            try memoryStore.recordKnownGoodPattern(
                title: "Reliable \(commandCategory) pattern",
                summary: "Command \(commandCategory) has repeated successful verified reuse in this workspace.",
                knowledgeClass: .reusable,
                affectedModules: decision.architectureFindings.flatMap(\.affectedModules),
                evidenceRefs: decision.projectMemoryRefs.map(\.path),
                sourceTraceIDs: [],
                body: """
                Command category: \(commandCategory)
                Workspace path: \(intent.workspaceRelativePath ?? "workspace-root")
                """
            )
        } catch {
            return
        }
    }

    public func recordRejectedApproach(
        title: String,
        taskContext: TaskContext,
        decision: PlannerDecision,
        body: String
    ) {
        let agentKind = taskContext.agentKind
        guard agentKind == .code || agentKind == .mixed else {
            return
        }
        if let root = taskContext.workspaceRoot {
            memoryStore.setWorkspaceRoot(root)
        }
        do {
            try memoryStore.recordRejectedApproach(
                title: title,
                summary: "Parallel experiment candidates did not produce a safe winner",
                knowledgeClass: .reusable,
                affectedModules: Array(Set(decision.architectureFindings.flatMap(\.affectedModules))).sorted(),
                evidenceRefs: decision.projectMemoryRefs.map(\.path),
                sourceTraceIDs: [],
                body: body
            )
        } catch {
            return
        }
    }
}
