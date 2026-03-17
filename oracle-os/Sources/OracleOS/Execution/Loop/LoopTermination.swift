import Foundation

public enum LoopTermination: Sendable {
    case continueRunning
    case finished(LoopOutcome)

    public var outcome: LoopOutcome? {
        if case let .finished(outcome) = self {
            return outcome
        }
        return nil
    }
}
