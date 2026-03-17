// MARK: - Command
// Oracle-OS vNext — Typed representation of an action.
// Commands are SCHEMA ONLY. They carry no execution logic.
// Planners produce Commands. VerifiedExecutor consumes Commands.

import Foundation

// MARK: CommandID

public struct CommandID: Sendable, Codable, Hashable, CustomStringConvertible {
    public let value: UUID
    public init(_ value: UUID = UUID()) { self.value = value }
    public var description: String { value.uuidString }
}

// MARK: CommandMetadata

public struct CommandMetadata: Sendable, Codable {
    public let intentID: UUID
    public let planningStrategy: String
    public let rationale: String
    public let timestamp: Date
    public let confidence: Double

    public init(
        intentID: UUID,
        planningStrategy: String = "unknown",
        rationale: String = "",
        timestamp: Date = Date(),
        confidence: Double = 1.0
    ) {
        self.intentID = intentID
        self.planningStrategy = planningStrategy
        self.rationale = rationale
        self.timestamp = timestamp
        self.confidence = confidence
    }
}

// MARK: Command Protocol

/// Sealed command type. Planners return this. Executors dispatch on it.
/// INVARIANT: Commands must never be self-executing.
public protocol Command: Sendable {
    var id: CommandID { get }
    var kind: String { get }
    var metadata: CommandMetadata { get }
}
