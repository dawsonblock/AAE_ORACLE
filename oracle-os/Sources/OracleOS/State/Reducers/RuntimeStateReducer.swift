import Foundation
public struct RuntimeStateReducer: EventReducer {
    public init() {}
    public func apply(events: [EventEnvelope], to state: inout WorldStateModel) {
        _ = events
    }
}
