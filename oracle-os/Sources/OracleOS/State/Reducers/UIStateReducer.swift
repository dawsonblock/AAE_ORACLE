import Foundation
public struct UIStateReducer: EventReducer {
    public init() {}
    public func apply(events: [EventEnvelope], to state: inout WorldStateModel) {
        // UI state changes derived from observation events
        _ = events
    }
}
