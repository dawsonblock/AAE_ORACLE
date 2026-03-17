import Foundation

/// The return type of VerifiedExecutor.
/// INVARIANT: Executor returns events and artifacts ONLY — no committed state writes.
public struct ExecutionOutcome: Sendable {
    public let commandID: CommandID
    public let status: ExecutionStatus
    public let observations: [ObservationPayload]
    public let artifacts: [ArtifactPayload]
    public let events: [EventEnvelope]
    public let verifierReport: VerifierReport

    public init(commandID: CommandID, status: ExecutionStatus, observations: [ObservationPayload] = [],
                artifacts: [ArtifactPayload] = [], events: [EventEnvelope], verifierReport: VerifierReport) {
        self.commandID = commandID; self.status = status; self.observations = observations
        self.artifacts = artifacts; self.events = events; self.verifierReport = verifierReport
    }
}

public enum ExecutionStatus: String, Sendable, Codable {
    case success, failed, partialSuccess, preconditionFailed, policyBlocked, postconditionFailed
}

public struct VerifierReport: Sendable, Codable {
    public let commandID: CommandID
    public let preconditionsPassed: Bool
    public let policyDecision: String
    public let postconditionsPassed: Bool
    public let notes: [String]
    public let timestamp: Date

    public init(commandID: CommandID, preconditionsPassed: Bool, policyDecision: String,
                postconditionsPassed: Bool, notes: [String] = [], timestamp: Date = Date()) {
        self.commandID = commandID; self.preconditionsPassed = preconditionsPassed
        self.policyDecision = policyDecision; self.postconditionsPassed = postconditionsPassed
        self.notes = notes; self.timestamp = timestamp
    }
}

public struct ObservationPayload: Sendable, Codable {
    public let kind: String; public let content: String; public let timestamp: Date
    public init(kind: String, content: String, timestamp: Date = Date()) {
        self.kind = kind; self.content = content; self.timestamp = timestamp }
}

public struct ArtifactPayload: Sendable, Codable {
    public let kind: String; public let identifier: String; public let data: Data?
    public init(kind: String, identifier: String, data: Data? = nil) {
        self.kind = kind; self.identifier = identifier; self.data = data }
}
