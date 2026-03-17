import Foundation

// MARK: - Phase 3: Path Resolution Result

/// Result of path resolution from AAE hints or Oracle query
public struct PathResolutionResult: Sendable, Equatable {
    /// The resolved path to use
    public let resolvedPath: String
    
    /// Source of the resolution
    public let source: PathSource
    
    /// Resolution status
    public let status: ResolutionStatus
    
    /// Original requested path (if different from resolved)
    public let requestedPath: String?
    
    /// Candidate ID if from AAE
    public let candidateId: String?
    
    public enum PathSource: String, Sendable, Equatable {
        case aaeHint = "aae_hint"
        case oracleQuery = "oracle_query"
        case fallback = "fallback"
    }
    
    public enum ResolutionStatus: String, Sendable, Equatable {
        case success = "success"
        case fileNotFound = "file_not_found"
        case fallbackUsed = "fallback_used"
    }
    
    public init(
        resolvedPath: String,
        source: PathSource,
        status: ResolutionStatus,
        requestedPath: String? = nil,
        candidateId: String? = nil
    ) {
        self.resolvedPath = resolvedPath
        self.source = source
        self.status = status
        self.requestedPath = requestedPath
        self.candidateId = candidateId
    }
}

public enum CodeSkillResolutionError: Error, Sendable, Equatable {
    case missingWorkspace
    case noRepositorySnapshot
    case noRelevantFiles(String)
    case ambiguousEditTarget(String)

    public var failureClass: FailureClass {
        switch self {
        case .missingWorkspace:
            return .workspaceScopeViolation
        case .noRepositorySnapshot, .noRelevantFiles:
            return .noRelevantFiles
        case .ambiguousEditTarget:
            return .ambiguousEditTarget
        }
    }
}

enum CodeSkillSupport {
    static func workspaceRoot(taskContext: TaskContext, state: WorldState) throws -> URL {
        if let workspaceRoot = taskContext.workspaceRoot {
            return URL(fileURLWithPath: workspaceRoot, isDirectory: true)
        }
        if let snapshotRoot = state.repositorySnapshot?.workspaceRoot {
            return URL(fileURLWithPath: snapshotRoot, isDirectory: true)
        }
        throw CodeSkillResolutionError.missingWorkspace
    }

    static func repositorySnapshot(state: WorldState, workspaceRoot: URL) throws -> RepositorySnapshot {
        if let repositorySnapshot = state.repositorySnapshot {
            return repositorySnapshot
        }
        return RepositoryIndexer().indexIfNeeded(workspaceRoot: workspaceRoot)
    }

    // MARK: - Phase 3: resolveTargetPath
    
    /// Resolves the target path for skill execution, prioritizing AAE hints
    /// - Parameters:
    ///   - taskContext: The task context containing AAE path hints
    ///   - state: Current world state
    ///   - memoryStore: Memory store for fallback queries
    ///   - failureOutput: Optional failure output for root cause analysis
    ///   - skillName: Name of the skill requesting resolution
    /// - Returns: PathResolutionResult with resolved path and metadata
    static func resolveTargetPath(
        from taskContext: TaskContext,
        state: WorldState,
        memoryStore: UnifiedMemoryStore,
        failureOutput: String? = nil,
        skillName: String? = nil
    ) throws -> PathResolutionResult {
        let workspaceRoot = try workspaceRoot(taskContext: taskContext, state: state)
        let snapshot = try repositorySnapshot(state: state, workspaceRoot: workspaceRoot)
        
        // Phase 3: Check for AAE target path hints first (highest priority)
        if let aaeTargetPath = taskContext.targetFile {
            // Check if AAE target path exists in the workspace
            let exists = snapshot.files.contains { 
                $0.path == aaeTargetPath && !$0.isDirectory 
            }
            
            if exists {
                // AAE hint found and file exists - use it
                return PathResolutionResult(
                    resolvedPath: aaeTargetPath,
                    source: .aaeHint,
                    status: .success,
                    requestedPath: aaeTargetPath,
                    candidateId: taskContext.aaeCandidateID
                )
            } else {
                // AAE hint provided but file doesn't exist - log warning and fall back
                // Try ranked fallback paths from AAE
                if let fallbackPaths = taskContext.rankedFallbackPaths {
                    for fallbackPath in fallbackPaths {
                        if snapshot.files.contains(where: { $0.path == fallbackPath && !$0.isDirectory }) {
                            return PathResolutionResult(
                                resolvedPath: fallbackPath,
                                source: .aaeHint,
                                status: .fileNotFound,
                                requestedPath: aaeTargetPath,
                                candidateId: taskContext.aaeCandidateID
                            )
                        }
                    }
                }
                
                // No valid fallback from AAE, fall back to Oracle query
                let oraclePath = try resolveViaOracleQuery(
                    taskContext: taskContext,
                    state: state,
                    memoryStore: memoryStore,
                    workspaceRoot: workspaceRoot,
                    snapshot: snapshot,
                    failureOutput: failureOutput
                )
                return PathResolutionResult(
                    resolvedPath: oraclePath,
                    source: .oracleQuery,
                    status: .fileNotFound,
                    requestedPath: aaeTargetPath,
                    candidateId: taskContext.aaeCandidateID
                )
            }
        }
        
        // No AAE hint - use Oracle query or fallback
        let oraclePath = try resolveViaOracleQuery(
            taskContext: taskContext,
            state: state,
            memoryStore: memoryStore,
            workspaceRoot: workspaceRoot,
            snapshot: snapshot,
            failureOutput: failureOutput
        )
        return PathResolutionResult(
            resolvedPath: oraclePath,
            source: .oracleQuery,
            status: .success,
            candidateId: nil
        )
    }
    
    /// Resolve path via Oracle code query (existing logic)
    private static func resolveViaOracleQuery(
        taskContext: TaskContext,
        state: WorldState,
        memoryStore: UnifiedMemoryStore,
        workspaceRoot: URL,
        snapshot: RepositorySnapshot,
        failureOutput: String?
    ) throws -> String {
        // First check planner preferred path
        if let plannerPreferredPath = taskContext.plannerPreferredPath,
           snapshot.files.contains(where: { $0.path == plannerPreferredPath && !$0.isDirectory }) {
            return plannerPreferredPath
        }
        
        // Check memory influence
        let memoryInfluence = MemoryRouter(memoryStore: memoryStore).influence(
            for: MemoryQueryContext(
                taskContext: taskContext,
                worldState: state,
                errorSignature: failureOutput
            )
        )
        
        if let preferredPath = memoryInfluence.preferredFixPath {
            return preferredPath
        }
        
        // Use code query engine
        let queryEngine = CodeQueryEngine()
        var rankedMatches: [RankedCodeCandidate] = []
        if let failureOutput, !failureOutput.isEmpty {
            rankedMatches = queryEngine.findLikelyRootCause(
                failureDescription: failureOutput,
                in: snapshot
            )
        }
        
        if let best = rankedMatches.first {
            if let next = rankedMatches.dropFirst().first,
               abs(best.score - next.score) < 0.15,
               best.path != next.path
            {
                throw CodeSkillResolutionError.ambiguousEditTarget(
                    rankedMatches.prefix(3).map(\.path).joined(separator: ", ")
                )
            }
            return best.path
        }
        
        // Final fallback - find any relevant file
        let fallbackMatches = snapshot.files
                .filter { !$0.isDirectory && ($0.path.hasSuffix(".swift") || $0.path.hasSuffix(".ts") || $0.path.hasSuffix(".js")) }
                .map(\.path)
        guard let first = fallbackMatches.first else {
            throw CodeSkillResolutionError.noRelevantFiles(taskContext.goal.description)
        }
        if fallbackMatches.count > 1 {
            let rest = fallbackMatches.dropFirst()
            if rest.contains(where: { $0 != first }) {
                throw CodeSkillResolutionError.ambiguousEditTarget(fallbackMatches.prefix(3).joined(separator: ", "))
            }
        }
        return first
    }

    static func preferredPath(
        taskContext: TaskContext,
        state: WorldState,
        memoryStore: UnifiedMemoryStore,
        failureOutput: String? = nil
    ) throws -> String {
        // Phase 3: Use resolveTargetPath which prioritizes AAE hints
        let resolutionResult = try resolveTargetPath(
            from: taskContext,
            state: state,
            memoryStore: memoryStore,
            failureOutput: failureOutput
        )
        return resolutionResult.resolvedPath
    }

    static func command(
        category: CodeCommandCategory,
        workspaceRoot: URL,
        workspaceRelativePath: String? = nil,
        summary: String,
        arguments: [String] = [],
        touchesNetwork: Bool = false
    ) -> CommandSpec {
        CommandSpec(
            category: category,
            executable: "/usr/bin/env",
            arguments: arguments,
            workspaceRoot: workspaceRoot.path,
            workspaceRelativePath: workspaceRelativePath,
            summary: summary,
            touchesNetwork: touchesNetwork
        )
    }
}
