import Foundation

/// Validates preconditions before command execution.
/// Returns false if required conditions are not met.
public struct PreconditionsValidator: Sendable {
    public init() {}
    
    public func validate(_ command: any Command, state: WorldStateModel) throws -> Bool {
        // Get current state snapshot for validation
        let snapshot = state.snapshot
        
        // Validate based on command domain
        switch command.kind {
        // UI Commands require active application context
        case "clickElement", "typeText", "focusWindow", "readElement":
            guard snapshot.activeApplication != nil else {
                throw PreconditionError.noActiveApplication
            }
            guard !snapshot.modalPresent else {
                throw PreconditionError.modalPresent
            }
            
        // Code Commands require repository context
        case "searchRepository", "modifyFile", "runBuild", "runTests", "readFile":
            guard snapshot.repositoryRoot != nil else {
                throw PreconditionError.noRepositoryContext
            }
            // Block dangerous operations on dirty git state
            if command.kind == "modifyFile" && snapshot.isGitDirty {
                throw PreconditionError.gitDirty
            }
            
        // System Commands require app context and no modal
        case "launchApp", "openURL":
            guard !snapshot.modalPresent else {
                throw PreconditionError.modalPresent
            }
            
        default:
            // Unknown command kind - fail safe
            throw PreconditionError.unknownCommand(command.kind)
        }
        
        // Validate metadata has required intent ID
        let zeroUUID = UUID(uuidString: "00000000-0000-0000-0000-000000000000")!
        guard command.metadata.intentID != zeroUUID else {
            throw PreconditionError.invalidIntentID
        }
        
        // Validate confidence threshold
        guard command.metadata.confidence >= 0.5 else {
            throw PreconditionError.lowConfidence(command.metadata.confidence)
        }
        
        return true
    }
}

/// Errors thrown by PreconditionsValidator
public enum PreconditionError: Error, CustomStringConvertible {
    case noActiveApplication
    case modalPresent
    case noRepositoryContext
    case gitDirty
    case unknownCommand(String)
    case invalidIntentID
    case lowConfidence(Double)
    
    public var description: String {
        switch self {
        case .noActiveApplication: return "No active application context"
        case .modalPresent: return "Modal dialog present - cannot execute"
        case .noRepositoryContext: return "No repository context for code command"
        case .gitDirty: return "Git working directory is dirty"
        case .unknownCommand(let kind): return "Unknown command kind: \(kind)"
        case .invalidIntentID: return "Invalid or missing intent ID in metadata"
        case .lowConfidence(let confidence): return "Confidence \(confidence) below threshold 0.5"
        }
    }
}
