import Foundation
public struct ProjectStateReducer: EventReducer {
    public init() {}
    public func apply(events: [EventEnvelope], to state: inout WorldStateModel) {
        // Project state changes derived from events are handled by WorldStateModel
        _ = events
    }
}
