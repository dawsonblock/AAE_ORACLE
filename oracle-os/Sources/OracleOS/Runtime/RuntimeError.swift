import Foundation

public enum RuntimeError: Error, Sendable {
    case invalidIntent(String)
    case planningFailed(String)
    case executionFailed(String)
    case commitFailed(String)
    case stateCorrupted(String)
    case unknown(String)

    public var description: String {
        switch self {
        case .invalidIntent(let msg): return "Invalid intent: \(msg)"
        case .planningFailed(let msg): return "Planning failed: \(msg)"
        case .executionFailed(let msg): return "Execution failed: \(msg)"
        case .commitFailed(let msg): return "Commit failed: \(msg)"
        case .stateCorrupted(let msg): return "State corrupted: \(msg)"
        case .unknown(let msg): return "Unknown error: \(msg)"
        }
    }
}
