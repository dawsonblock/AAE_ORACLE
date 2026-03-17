public struct WorldState: Sendable {
    public var observationHash: String
    public var planningState: PlanningState
    public var beliefStateID: String?

    public var observation: Observation
    public var repositorySnapshot: RepositorySnapshot?

    public var lastAction: ActionIntent?

    public init(
        observation: Observation,
        lastAction: ActionIntent? = nil,
        beliefStateID: String? = nil,
        repositorySnapshot: RepositorySnapshot? = nil,
        stateAbstraction: StateAbstraction = StateAbstraction()
    ) {
        let observationHash = ObservationHash.hash(observation)
        self.observationHash = observationHash
        self.planningState = stateAbstraction.abstract(
            observation: observation,
            repositorySnapshot: repositorySnapshot,
            observationHash: observationHash
        )
        self.beliefStateID = beliefStateID
        self.observation = observation
        self.repositorySnapshot = repositorySnapshot
        self.lastAction = lastAction
    }

    public init(
        observationHash: String,
        planningState: PlanningState,
        beliefStateID: String? = nil,
        observation: Observation,
        repositorySnapshot: RepositorySnapshot? = nil,
        lastAction: ActionIntent? = nil
    ) {
        self.observationHash = observationHash
        self.planningState = planningState
        self.beliefStateID = beliefStateID
        self.observation = observation
        self.repositorySnapshot = repositorySnapshot
        self.lastAction = lastAction
    }
}
