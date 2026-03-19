import Foundation

// AgentLoop is the authoritative runtime spine for orchestration only.
// It may request state, decision, execution, learning, and recovery stages,
// then terminate or continue. It must not absorb ranking, graph scoring,
// experiment comparison, or direct world mutation logic.
@MainActor
public final class AgentLoop {
    let planner: MainPlanner
    let graphStore: GraphStore
    let experimentCoordinator: LoopExperimentCoordinator
    let learningCoordinator: LearningCoordinator
    let stateCoordinator: StateCoordinator
    let decisionCoordinator: DecisionCoordinator
    let executionCoordinator: ExecutionCoordinator
    let recoveryCoordinator: RecoveryCoordinator
    private let stateMemoryIndex: StateMemoryIndex?
    let worldModel: WorldStateModel
    let aaePlanningAdvisor: OracleAAEPlanningAdvisor?

    /// NEW: IntentAPI-based orchestrator for the new execution spine.
    /// When set, the run loop should prefer this over legacy coordinator path.
    public let orchestrator: any IntentAPI

    /// NEW preferred init — uses RuntimeOrchestrator as the execution spine.
    /// This is the target architecture: AgentLoop becomes a thin wrapper that
    /// submits intents through RuntimeOrchestrator.
    public init(
        orchestrator: any IntentAPI,
        observationProvider: any ObservationProvider,
        executionDriver: any AgentExecutionDriver,
        stateAbstraction: StateAbstraction = StateAbstraction(),
        planner: MainPlanner = MainPlanner(),
        graphStore: GraphStore = GraphStore(),
        policyEngine: PolicyEngine = PolicyEngine(),
        recoveryEngine: RecoveryEngine = RecoveryEngine(),
        memoryStore: UnifiedMemoryStore = UnifiedMemoryStore(),
        skillRegistry: SkillRegistry = .live(),
        repositoryIndexer: RepositoryIndexer = RepositoryIndexer(),
        experimentManager: ExperimentManager = ExperimentManager(),
        automationHost: AutomationHost = .live(),
        browserPageStateBuilder: BrowserPageStateBuilder = BrowserPageStateBuilder(),
        stateMemoryIndex: StateMemoryIndex? = nil,
        worldModel: WorldStateModel = WorldStateModel()
    ) {
        self.orchestrator = orchestrator
        self.planner = planner
        self.graphStore = graphStore
        self.stateMemoryIndex = stateMemoryIndex
        self.worldModel = worldModel
        self.aaePlanningAdvisor = OracleAAEPlanningAdvisor.loadFromEnvironment()

        let projectMemoryCoordinator = LoopProjectMemoryCoordinator(memoryStore: memoryStore)
        let learningCoordinator = LearningCoordinator(
            memoryStore: memoryStore,
            projectMemoryCoordinator: projectMemoryCoordinator
        )
        self.learningCoordinator = learningCoordinator
        self.stateCoordinator = StateCoordinator(
            observationProvider: observationProvider,
            stateAbstraction: stateAbstraction,
            repositoryIndexer: repositoryIndexer,
            automationHost: automationHost,
            browserPageStateBuilder: browserPageStateBuilder
        )
        self.decisionCoordinator = DecisionCoordinator(
            planner: planner,
            graphStore: graphStore,
            memoryStore: memoryStore,
            stateMemoryIndex: stateMemoryIndex
        )
        self.executionCoordinator = ExecutionCoordinator(
            executionDriver: executionDriver,
            skillRegistry: skillRegistry,
            policyEngine: policyEngine,
            memoryStore: memoryStore
        )
        self.recoveryCoordinator = RecoveryCoordinator(
            observationProvider: observationProvider,
            stateAbstraction: stateAbstraction,
            recoveryEngine: recoveryEngine,
            executionCoordinator: self.executionCoordinator,
            learningCoordinator: learningCoordinator,
            repositoryIndexer: repositoryIndexer,
            automationHost: automationHost,
            browserPageStateBuilder: browserPageStateBuilder
        )
        self.experimentCoordinator = LoopExperimentCoordinator(
            experimentManager: experimentManager,
            executionCoordinator: self.executionCoordinator,
            observationProvider: observationProvider,
            stateAbstraction: stateAbstraction,
            recoveryEngine: recoveryEngine,
            memoryStore: memoryStore,
            repositoryIndexer: repositoryIndexer,
            projectMemoryCoordinator: projectMemoryCoordinator
        )
    }

    public func execute(goal: Goal) {
        Task { [weak self] in
            guard let self else { return }
            _ = await self.run(goal: goal)
        }
    }
}
