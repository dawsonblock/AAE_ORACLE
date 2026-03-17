import Foundation

/// Wraps a DomainEvent with routing metadata for the event store.
public struct EventEnvelope: Sendable, Codable {
    public let id: UUID
    public let sequenceNumber: Int
    public let commandID: CommandID?
    public let intentID: UUID?
    public let timestamp: Date
    public let eventType: String
    public let payload: Data   // JSON-encoded DomainEvent

    public init(id: UUID = UUID(), sequenceNumber: Int, commandID: CommandID?, intentID: UUID?,
                timestamp: Date = Date(), eventType: String, payload: Data) {
        self.id = id; self.sequenceNumber = sequenceNumber; self.commandID = commandID
        self.intentID = intentID; self.timestamp = timestamp; self.eventType = eventType; self.payload = payload
    }
}
