import Foundation

/// The ONLY layer allowed to produce side effects in Oracle-OS.
/// 
/// INVARIANTS:
///   - Executor observes and acts, but does NOT commit state
///   - Executor returns ExecutionOutcome with events and artifacts only
///   - CommitCoordinator is the ONLY entity that writes committed state
public actor VerifiedExecutor {
    private let preconditionsValidator: PreconditionsValidator
    private let safetyValidator: SafetyValidator
    private let capabilityBinder: CapabilityBinder
    private let toolDispatcher: ToolDispatcher
    private let postconditionsValidator: PostconditionsValidator

    public init(
        preconditionsValidator: PreconditionsValidator = PreconditionsValidator(),
        safetyValidator: SafetyValidator = SafetyValidator(),
        capabilityBinder: CapabilityBinder = CapabilityBinder(),
        toolDispatcher: ToolDispatcher = ToolDispatcher(),
        postconditionsValidator: PostconditionsValidator = PostconditionsValidator()
    ) {
        self.preconditionsValidator = preconditionsValidator
        self.safetyValidator = safetyValidator
        self.capabilityBinder = capabilityBinder
        self.toolDispatcher = toolDispatcher
        self.postconditionsValidator = postconditionsValidator
    }

    /// Execute a validated command and return outcome with events.
    /// IMPORTANT: This does NOT commit state — only returns events for CommitCoordinator.
    public func execute(_ command: any Command, state: WorldStateModel) async throws -> ExecutionOutcome {
        // Phase 1: Preconditions
        guard try preconditionsValidator.validate(command, state: state) else {
            return failOutcome(command: command, status: .preconditionFailed, reason: "Preconditions failed")
        }

        // Phase 2: Safety validation
        let safety = safetyValidator.isSafe(command, state: state)
        guard safety.safe else {
            return failOutcome(command: command, status: .policyBlocked, reason: safety.reason)
        }

        // Phase 3: Capability binding
        let capabilities = try capabilityBinder.bind(command)

        // Phase 4: Action execution
        let (observations, artifacts) = try await toolDispatcher.dispatch(command, capabilities: capabilities)

        // Phase 5: Postconditions
        let initialOutcome = ExecutionOutcome(
            commandID: command.id,
            status: .success,
            observations: observations,
            artifacts: artifacts,
            events: [],
            verifierReport: VerifierReport(commandID: command.id, preconditionsPassed: true, policyDecision: "approved", postconditionsPassed: true)
        )

        guard try postconditionsValidator.validate(command, outcome: initialOutcome) else {
            return failOutcome(command: command, status: .postconditionFailed, reason: "Postconditions failed")
        }

        // Return outcome — commit happens in RuntimeOrchestrator
        return initialOutcome
    }

    private func failOutcome(command: any Command, status: ExecutionStatus, reason: String) -> ExecutionOutcome {
        let report = VerifierReport(
            commandID: command.id,
            preconditionsPassed: status != .preconditionFailed,
            policyDecision: status == .policyBlocked ? reason : "approved",
            postconditionsPassed: status != .postconditionFailed,
            notes: [reason]
        )
        return ExecutionOutcome(commandID: command.id, status: status, events: [], verifierReport: report)
    }
}
