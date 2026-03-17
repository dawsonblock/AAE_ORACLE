import Foundation
public struct MemoryStateReducer: EventReducer {
    public init() {}
    public func apply(events: [EventEnvelope], to state: inout WorldStateModel) {
        // Memory promotion tracked via learning events only — no direct state writes here
    }
}
