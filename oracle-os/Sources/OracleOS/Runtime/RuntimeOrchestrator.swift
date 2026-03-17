import Foundation

/// The single entry point for runtime cycle execution.
/// Coordinates: decide → execute → commit → evaluate
public actor RuntimeOrchestrator: IntentAPI {
    private let eventStore: EventStore
    private let commitCoordinator: CommitCoordinator
    // The planner used for intent processing in submitIntent
    private let planner: any Planner
    // LEGACY: remove when performAction is eliminated
    private let preconditionsValidator: PreconditionsValidator
    // LEGACY: remove when performAction is eliminated
    private let safetyValidator: SafetyValidator
    // LEGACY: remove when performAction is eliminated
    private let toolDispatcher: ToolDispatcher
    // LEGACY: remove when performAction is eliminated
    private let postconditionsValidator: PostconditionsValidator
    // LEGACY: remove when performAction is eliminated
    private let capabilityBinder: CapabilityBinder
    nonisolated(unsafe) public var _legacyContext: RuntimeContext?

    /// The authoritative execution delegate — only layer allowed to produce side effects.
    private let verifiedExecutor: VerifiedExecutor

    public init(
        eventStore: EventStore,
        commitCoordinator: CommitCoordinator,
        planner: any Planner,
        preconditionsValidator: PreconditionsValidator = PreconditionsValidator(),
        safetyValidator: SafetyValidator = SafetyValidator(),
        toolDispatcher: ToolDispatcher = ToolDispatcher(),
        postconditionsValidator: PostconditionsValidator = PostconditionsValidator(),
        capabilityBinder: CapabilityBinder = CapabilityBinder(),
        context: RuntimeContext? = nil
    ) {
        self.eventStore = eventStore
        self.commitCoordinator = commitCoordinator
        self.planner = planner
        self.preconditionsValidator = preconditionsValidator
        self.safetyValidator = safetyValidator
        self.toolDispatcher = toolDispatcher
        self.postconditionsValidator = postconditionsValidator
        self.capabilityBinder = capabilityBinder
        self._legacyContext = context
        self.verifiedExecutor = VerifiedExecutor(
            preconditionsValidator: preconditionsValidator,
            safetyValidator: safetyValidator,
            capabilityBinder: capabilityBinder,
            toolDispatcher: toolDispatcher,
            postconditionsValidator: postconditionsValidator
        )
    }

    public init(
        eventStore: EventStore,
        commitCoordinator: CommitCoordinator,
        context: RuntimeContext? = nil
    ) {
        self.eventStore = eventStore
        self.commitCoordinator = commitCoordinator
        self.planner = MainPlanner()
        self.preconditionsValidator = PreconditionsValidator()
        self.safetyValidator = SafetyValidator()
        self.toolDispatcher = ToolDispatcher()
        self.postconditionsValidator = PostconditionsValidator()
        self.capabilityBinder = CapabilityBinder()
        self._legacyContext = context
        self.verifiedExecutor = VerifiedExecutor(
            preconditionsValidator: self.preconditionsValidator,
            safetyValidator: self.safetyValidator,
            capabilityBinder: self.capabilityBinder,
            toolDispatcher: self.toolDispatcher,
            postconditionsValidator: self.postconditionsValidator
        )
    }

    /// Backward-compatibility initializer for callers that only have a RuntimeContext.
    public init(context: RuntimeContext, planner: any Planner) {
        self.eventStore = EventStore()
        self.commitCoordinator = CommitCoordinator(eventStore: self.eventStore, reducers: [])
        self.planner = planner
        self.preconditionsValidator = PreconditionsValidator()
        self.safetyValidator = SafetyValidator()
        self.toolDispatcher = ToolDispatcher()
        self.postconditionsValidator = PostconditionsValidator()
        self.capabilityBinder = CapabilityBinder()
        self._legacyContext = context
        self.verifiedExecutor = VerifiedExecutor(
            preconditionsValidator: self.preconditionsValidator,
            safetyValidator: self.safetyValidator,
            capabilityBinder: self.capabilityBinder,
            toolDispatcher: self.toolDispatcher,
            postconditionsValidator: self.postconditionsValidator
        )
    }

    /// Legacy initializer - creates default MainPlanner internally for backward compatibility
    public init(context: RuntimeContext) {
        self.eventStore = EventStore()
        self.commitCoordinator = CommitCoordinator(eventStore: self.eventStore, reducers: [])
        self.planner = MainPlanner()
        self.preconditionsValidator = PreconditionsValidator()
        self.safetyValidator = SafetyValidator()
        self.toolDispatcher = ToolDispatcher()
        self.postconditionsValidator = PostconditionsValidator()
        self.capabilityBinder = CapabilityBinder()
        self._legacyContext = context
        self.verifiedExecutor = VerifiedExecutor(
            preconditionsValidator: self.preconditionsValidator,
            safetyValidator: self.safetyValidator,
            capabilityBinder: self.capabilityBinder,
            toolDispatcher: self.toolDispatcher,
            postconditionsValidator: self.postconditionsValidator
        )
    }

    /// PHASE 1: Decide — invoke planner to produce a Command
    public func decide(intent: Intent, planner: any Planner) async throws -> any Command {
        let context = PlannerContext(state: WorldStateModel())
        return try await planner.plan(intent: intent, context: context)
    }

    /// PHASE 2: Execute — delegates to VerifiedExecutor (the single side-effect layer)
    public func execute(_ command: any Command, state: WorldStateModel) async throws -> ExecutionOutcome {
        // Delegate the full validation + dispatch pipeline to VerifiedExecutor
        let rawOutcome = try await verifiedExecutor.execute(command, state: state)

        // Build event envelopes from the outcome
        let events = buildEvents(
            from: command,
            observations: rawOutcome.observations,
            artifacts: rawOutcome.artifacts,
            status: rawOutcome.status
        )

        // Return a new outcome with events attached
        return ExecutionOutcome(
            commandID: rawOutcome.commandID,
            status: rawOutcome.status,
            observations: rawOutcome.observations,
            artifacts: rawOutcome.artifacts,
            events: events,
            verifierReport: rawOutcome.verifierReport
        )
    }
    
    /// Build event envelopes from execution results
    private func buildEvents(from command: any Command, observations: [ObservationPayload], artifacts: [ArtifactPayload], status: ExecutionStatus) -> [EventEnvelope] {
        var events: [EventEnvelope] = []
        
        // Encode payload to Data
        func encodePayload(_ dict: [String: String]) -> Data {
            try! JSONSerialization.data(withJSONObject: dict)
        }
        
        // Action started event
        let startPayload = encodePayload([
            "commandKind": command.kind,
            "intentID": command.metadata.intentID.uuidString
        ])
        
        events.append(EventEnvelope(
            id: UUID(),
            sequenceNumber: 0, // Will be assigned by EventStore
            commandID: command.id,
            intentID: command.metadata.intentID,
            timestamp: Date(),
            eventType: "actionStarted",
            payload: startPayload
        ))
        
        // Action completed/failed event
        let eventType = status == .success ? "actionCompleted" : "actionFailed"
        var payloadDict: [String: String] = [
            "commandKind": command.kind,
            "status": status.rawValue
        ]
        
        if status == .success && !observations.isEmpty {
            payloadDict["observationCount"] = String(observations.count)
        }
        
        let endPayload = encodePayload(payloadDict)
        
        events.append(EventEnvelope(
            id: UUID(),
            sequenceNumber: 0, // Will be assigned by EventStore
            commandID: command.id,
            intentID: command.metadata.intentID,
            timestamp: Date(),
            eventType: eventType,
            payload: endPayload
        ))
        
        return events
    }

    /// PHASE 3: Commit — event-sourced state mutation
    public func commit(_ outcome: ExecutionOutcome) async throws {
        try await commitCoordinator.commit(outcome.events)
    }

    /// PHASE 4: Evaluate — critic review (stub)
    public func evaluate(_ outcome: ExecutionOutcome) async { /* critic loop stub */ }
}

// MARK: - IntentAPI Conformance

extension RuntimeOrchestrator {
    /// Submit a user or system intent for execution.
    /// Full pipeline: Plan → Validate → Execute → Emit Events → Commit → Snapshot
    public func submitIntent(_ intent: Intent) async throws -> IntentResponse {
        let cycleID = UUID()
        
        // 1. Plan - invoke planner to produce a Command
        let context = PlannerContext(state: WorldStateModel())
        let command: any Command
        do {
            command = try await planner.plan(intent: intent, context: context)
        } catch {
            return IntentResponse(
                intentID: intent.id,
                outcome: .failed,
                summary: "Planning failed: \(error.localizedDescription)",
                cycleID: cycleID,
                snapshotID: nil,
                timestamp: Date()
            )
        }
        
        // 2. Validate - PolicyEngine checks the command
        // Create ActionIntent from command metadata for policy evaluation
        let actionIntent = ActionIntent(
            agentKind: .os,
            app: "unknown",
            name: command.kind,
            action: command.kind,
            query: nil,
            text: nil,
            role: nil,
            domID: nil,
            x: nil,
            y: nil,
            button: nil,
            count: nil,
            workspaceRoot: ".",
            workspaceRelativePath: nil,
            codeCommand: nil,
            postconditions: []
        )
        let policyDecision = PolicyEngine.shared.evaluate(intent: actionIntent)
        
        guard policyDecision.allowed else {
            return IntentResponse(
                intentID: intent.id,
                outcome: .failed,
                summary: "Policy blocked: \(policyDecision.reason ?? "Action not allowed")",
                cycleID: cycleID,
                snapshotID: nil,
                timestamp: Date()
            )
        }
        
        // 3. Execute - delegate to VerifiedExecutor
        let executionOutcome: ExecutionOutcome
        do {
            executionOutcome = try await verifiedExecutor.execute(command, state: context.state)
        } catch {
            return IntentResponse(
                intentID: intent.id,
                outcome: .failed,
                summary: "Execution failed: \(error.localizedDescription)",
                cycleID: cycleID,
                snapshotID: nil,
                timestamp: Date()
            )
        }
        
        // 4. Emit events - build event envelopes from execution result
        let events = buildEvents(
            from: command,
            observations: executionOutcome.observations,
            artifacts: executionOutcome.artifacts,
            status: executionOutcome.status
        )
        
        // 5. Commit - event-sourced state mutation
        do {
            try await commitCoordinator.commit(events)
        } catch {
            return IntentResponse(
                intentID: intent.id,
                outcome: .partialSuccess,
                summary: "Execution succeeded but commit failed: \(error.localizedDescription)",
                cycleID: cycleID,
                snapshotID: nil,
                timestamp: Date()
            )
        }
        
        // 6. Snapshot - get current state snapshot
        let snapshotID = UUID()
        _ = await commitCoordinator.snapshot()
        
        // Determine outcome based on execution status
        let outcome: IntentResponse.Outcome
        switch executionOutcome.status {
        case .success:
            outcome = .success
        case .failed, .preconditionFailed, .postconditionFailed:
            outcome = .failed
        case .policyBlocked:
            outcome = .failed
        case .partialSuccess:
            outcome = .partialSuccess
        }
        
        return IntentResponse(
            intentID: intent.id,
            outcome: outcome,
            summary: "Intent completed: \(intent.objective) - \(executionOutcome.status.rawValue)",
            cycleID: cycleID,
            snapshotID: snapshotID,
            timestamp: Date()
        )
    }

    /// Read current committed world state as a snapshot (read-only).
    public func queryState() async throws -> RuntimeSnapshot {
        let snapshot = await commitCoordinator.snapshot()
        return RuntimeSnapshot(
            id: UUID(),
            timestamp: Date(),
            cycleCount: 0,
            lastIntentID: nil,
            lastCommandKind: nil,
            status: .idle,
            summary: "Runtime state: \(snapshot.visibleElementCount) visible elements, app: \(snapshot.activeApplication ?? "none")"
        )
    }
}
