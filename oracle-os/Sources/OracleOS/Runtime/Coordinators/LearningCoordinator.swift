import Foundation

/// Records learning outcomes into the trace / memory subsystem.
///
/// `LearningCoordinator` is a thin orchestration layer that delegates all
/// persistence work to ``LoopProjectMemoryCoordinator`` and ``MemoryUpdater``.
/// It does **not** plan or evaluate strategies — that responsibility belongs
/// exclusively to ``DecisionCoordinator``.
@MainActor
public final class LearningCoordinator {
    private let memoryStore: UnifiedMemoryStore
    private let projectMemoryCoordinator: LoopProjectMemoryCoordinator

    public var appMemoryStore: UnifiedMemoryStore { memoryStore }

    public init(
        memoryStore: UnifiedMemoryStore = UnifiedMemoryStore(),
        projectMemoryCoordinator: LoopProjectMemoryCoordinator
    ) {
        self.memoryStore = memoryStore
        self.projectMemoryCoordinator = projectMemoryCoordinator
    }

    public func recordSuccess(
        decision: PlannerDecision,
        intent: ActionIntent,
        taskContext: TaskContext
    ) {
        projectMemoryCoordinator.recordKnownGoodPattern(
            decision: decision,
            intent: intent,
            taskContext: taskContext
        )
        projectMemoryCoordinator.recordArchitectureDecision(
            decision: decision,
            taskContext: taskContext
        )
    }

    public func recordFailure(
        failure: FailureClass,
        stateBundle: LoopStateBundle
    ) {
        MemoryUpdater.recordFailure(
            failure: failure,
            state: stateBundle.worldState,
            store: memoryStore
        )
    }

    public func recordStrategy(
        app: String,
        strategy: String,
        success: Bool
    ) {
        memoryStore.recordStrategy(
            StrategyRecord(
                app: app,
                strategy: strategy,
                success: success
            )
        )
    }

    public func finalize(
        outcome: LoopOutcome,
        taskContext: TaskContext,
        decision: PlannerDecision?
    ) {
        guard outcome.reason != .goalAchieved else { return }
        projectMemoryCoordinator.recordOpenProblem(
            outcome: outcome,
            taskContext: taskContext,
            decision: decision
        )
    }
}
