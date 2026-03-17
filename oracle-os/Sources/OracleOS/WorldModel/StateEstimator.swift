import Foundation

/// Estimates a ``WorldState`` from a raw ``Observation`` when the full
/// state-building pipeline (``StateCoordinator``) is not available.
///
/// This is a lightweight fallback — the primary path always goes through
/// ``StateCoordinator.buildState()`` which produces richer context.
public struct StateEstimator: Sendable {
    public init() {}

    /// Produce a best-effort ``WorldState`` from a single observation.
    ///
    /// The returned state will have no repository snapshot or prior action
    /// context, but is safe to use for read-only planner queries and
    /// state-signature lookups.
    public func estimate(from observation: Observation) -> WorldState {
        WorldState(
            observation: observation,
            lastAction: nil,
            repositorySnapshot: nil,
            stateAbstraction: StateAbstraction()
        )
    }
}
