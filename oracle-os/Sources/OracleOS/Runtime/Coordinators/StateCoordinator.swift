import Foundation

/// Builds loop state from observations and manages the world-model subsystem.
///
/// `StateCoordinator` owns the observation → state-abstraction → task-graph
/// pipeline.  It pulls fresh observations, derives the current ``WorldState``,
/// and assembles the ``LoopStateBundle`` that downstream coordinators consume.
///
/// - Note: This coordinator does **not** record outcomes into memory stores;
///   that responsibility belongs to ``LearningCoordinator``.
@MainActor
public final class StateCoordinator {
    private let observationProvider: any ObservationProvider
    private let stateAbstraction: StateAbstraction
    private let repositoryIndexer: RepositoryIndexer
    private let automationHost: AutomationHost
    private let browserPageStateBuilder: BrowserPageStateBuilder
    private let taskGraphStore: TaskLedgerStore?

    public init(
        observationProvider: any ObservationProvider,
        stateAbstraction: StateAbstraction = StateAbstraction(),
        repositoryIndexer: RepositoryIndexer = RepositoryIndexer(),
        automationHost: AutomationHost = .live(),
        browserPageStateBuilder: BrowserPageStateBuilder = BrowserPageStateBuilder(),
        taskGraphStore: TaskLedgerStore? = nil
    ) {
        self.observationProvider = observationProvider
        self.stateAbstraction = stateAbstraction
        self.repositoryIndexer = repositoryIndexer
        self.automationHost = automationHost
        self.browserPageStateBuilder = browserPageStateBuilder
        self.taskGraphStore = taskGraphStore
    }

    public func buildState(
        taskContext: TaskContext,
        lastAction: ActionIntent?,
        recentFailureCount: Int = 0
    ) -> LoopStateBundle {
        let observation = observationProvider.observe()
        let repositorySnapshot = repositorySnapshot(for: taskContext)
        let worldState = WorldState(
            observation: observation,
            lastAction: lastAction,
            repositorySnapshot: repositorySnapshot,
            stateAbstraction: stateAbstraction
        )
        let memoryContext = MemoryQueryContext(taskContext: taskContext, worldState: worldState)

        // Update the task graph position from the observed world state.
        taskGraphStore?.updateCurrentNode(
            worldState: worldState,
            createdByAction: lastAction?.action
        )

        return LoopStateBundle(
            taskContext: taskContext,
            observation: observation,
            worldState: worldState,
            repositorySnapshot: repositorySnapshot,
            hostSnapshot: automationHost.snapshots.captureSnapshot(appName: observation.app),
            browserSession: browserPageStateBuilder.build(from: observation),
            memoryContext: memoryContext,
            recentFailureCount: recentFailureCount
        )
    }

    private func repositorySnapshot(for taskContext: TaskContext) -> RepositorySnapshot? {
        guard taskContext.agentKind == .code || taskContext.agentKind == .mixed,
              let workspaceRoot = taskContext.workspaceRoot
        else {
            return nil
        }
        return repositoryIndexer.indexIfNeeded(
            workspaceRoot: URL(fileURLWithPath: workspaceRoot, isDirectory: true)
        )
    }
}
