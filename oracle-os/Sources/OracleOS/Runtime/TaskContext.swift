import Foundation

// MARK: - Plan Source Markers (Phase 2: Planning Authority Normalization)

/// TaskContext plan source markers for Oracle-AAE fusion
/// Oracle remains the planner of record while AAE provides advisory candidates
public enum TaskPlanSource: String, Codable, Sendable {
    /// Oracle's own strong plan (internal confidence-based decision)
    case oracleNative = "oracle_native"
    /// Graph-backed/workflow-backed plan from Oracle
    case oracleGraph = "oracle_graph"
    /// AAE advisory candidates (validated but advisory only)
    case aaeAdvised = "aae_advised"
    /// Combined Oracle + AAE hybrid plan
    case oracleAAEHybrid = "oracle_aae_hybrid"
}

public struct TaskContext: Sendable, Codable, Equatable {
    public let goal: Goal
    public let agentKind: AgentKind
    public let workspaceRoot: String?
    public let phases: [TaskStepPhase]
    public let projectMemoryRoot: String?
    public let experimentsRoot: String?
    public let maxExperimentCandidates: Int
    public let experimentCandidates: [CandidatePatch]
    public let plannerPreferredPath: String?
    public let selectedCandidateID: String?
    public let candidateSource: TaskPlanSource?
    public let targetPathHints: [String]
    public let experimentBudget: Int?
    public let recommendedTestCommand: String?
    
    // MARK: - Phase 3: Structured Path Hints from AAE
    
    /// Primary target file path from AAE candidate
    public let targetFile: String?
    
    /// Ranked array of alternative fallback paths from AAE
    public let rankedFallbackPaths: [String]?
    
    /// Dominant programming language from AAE candidate
    public let dominantLanguage: String?
    
    /// Maximum number of files to modify (from AAE patch planning)
    public let patchFileCountLimit: Int?
    
    /// AAE candidate ID if source is AAE
    public let aaeCandidateID: String?

    public init(
        goal: Goal,
        agentKind: AgentKind,
        workspaceRoot: String? = nil,
        phases: [TaskStepPhase],
        projectMemoryRoot: String? = nil,
        experimentsRoot: String? = nil,
        maxExperimentCandidates: Int = 3,
        experimentCandidates: [CandidatePatch] = [],
        plannerPreferredPath: String? = nil,
        selectedCandidateID: String? = nil,
        candidateSource: TaskPlanSource? = nil,
        targetPathHints: [String] = [],
        experimentBudget: Int? = nil,
        recommendedTestCommand: String? = nil,
        // Phase 3 new fields
        targetFile: String? = nil,
        rankedFallbackPaths: [String]? = nil,
        dominantLanguage: String? = nil,
        patchFileCountLimit: Int? = nil,
        aaeCandidateID: String? = nil
    ) {
        self.goal = goal
        self.agentKind = agentKind
        self.workspaceRoot = workspaceRoot
        self.phases = phases
        self.projectMemoryRoot = projectMemoryRoot
        self.experimentsRoot = experimentsRoot
        self.maxExperimentCandidates = maxExperimentCandidates
        self.experimentCandidates = experimentCandidates
        self.plannerPreferredPath = plannerPreferredPath
        self.selectedCandidateID = selectedCandidateID
        self.candidateSource = candidateSource
        self.targetPathHints = targetPathHints
        self.experimentBudget = experimentBudget
        self.recommendedTestCommand = recommendedTestCommand
        self.targetFile = targetFile
        self.rankedFallbackPaths = rankedFallbackPaths
        self.dominantLanguage = dominantLanguage
        self.patchFileCountLimit = patchFileCountLimit
        self.aaeCandidateID = aaeCandidateID
    }

    public func with(plannerPreferredPath: String?) -> TaskContext {
        TaskContext(
            goal: goal,
            agentKind: agentKind,
            workspaceRoot: workspaceRoot,
            phases: phases,
            projectMemoryRoot: projectMemoryRoot,
            experimentsRoot: experimentsRoot,
            maxExperimentCandidates: maxExperimentCandidates,
            experimentCandidates: experimentCandidates,
            plannerPreferredPath: plannerPreferredPath,
            selectedCandidateID: selectedCandidateID,
            candidateSource: candidateSource,
            targetPathHints: targetPathHints,
            experimentBudget: experimentBudget,
            recommendedTestCommand: recommendedTestCommand,
            targetFile: targetFile,
            rankedFallbackPaths: rankedFallbackPaths,
            dominantLanguage: dominantLanguage,
            patchFileCountLimit: patchFileCountLimit,
            aaeCandidateID: aaeCandidateID
        )
    }

    // MARK: - Phase 2: Convenience method for updating AAE-related fields
    
    /// Returns a new TaskContext with AAE candidate information set
    public func withAAECandidate(
        candidateID: String,
        source: TaskPlanSource,
        targetPathHints: [String] = [],
        recommendedTestCommand: String? = nil,
        targetFile: String? = nil,
        rankedFallbackPaths: [String]? = nil,
        dominantLanguage: String? = nil,
        patchFileCountLimit: Int? = nil
    ) -> TaskContext {
        TaskContext(
            goal: goal,
            agentKind: agentKind,
            workspaceRoot: workspaceRoot,
            phases: phases,
            projectMemoryRoot: projectMemoryRoot,
            experimentsRoot: experimentsRoot,
            maxExperimentCandidates: maxExperimentCandidates,
            experimentCandidates: experimentCandidates,
            plannerPreferredPath: plannerPreferredPath,
            selectedCandidateID: candidateID,
            candidateSource: source,
            targetPathHints: targetPathHints,
            experimentBudget: experimentBudget,
            recommendedTestCommand: recommendedTestCommand ?? self.recommendedTestCommand,
            targetFile: targetFile ?? self.targetFile,
            rankedFallbackPaths: rankedFallbackPaths ?? self.rankedFallbackPaths,
            dominantLanguage: dominantLanguage ?? self.dominantLanguage,
            patchFileCountLimit: patchFileCountLimit ?? self.patchFileCountLimit,
            aaeCandidateID: candidateID
        )
    }
    
    /// Returns a new TaskContext with experiment budget set
    public func withExperimentBudget(_ budget: Int) -> TaskContext {
        TaskContext(
            goal: goal,
            agentKind: agentKind,
            workspaceRoot: workspaceRoot,
            phases: phases,
            projectMemoryRoot: projectMemoryRoot,
            experimentsRoot: experimentsRoot,
            maxExperimentCandidates: maxExperimentCandidates,
            experimentCandidates: experimentCandidates,
            plannerPreferredPath: plannerPreferredPath,
            selectedCandidateID: selectedCandidateID,
            candidateSource: candidateSource,
            targetPathHints: targetPathHints,
            experimentBudget: budget,
            recommendedTestCommand: recommendedTestCommand,
            targetFile: targetFile,
            rankedFallbackPaths: rankedFallbackPaths,
            dominantLanguage: dominantLanguage,
            patchFileCountLimit: patchFileCountLimit,
            aaeCandidateID: aaeCandidateID
        )
    }
    
    /// Returns a new TaskContext with recommended test command set
    public func withRecommendedTestCommand(_ command: String) -> TaskContext {
        TaskContext(
            goal: goal,
            agentKind: agentKind,
            workspaceRoot: workspaceRoot,
            phases: phases,
            projectMemoryRoot: projectMemoryRoot,
            experimentsRoot: experimentsRoot,
            maxExperimentCandidates: maxExperimentCandidates,
            experimentCandidates: experimentCandidates,
            plannerPreferredPath: plannerPreferredPath,
            selectedCandidateID: selectedCandidateID,
            candidateSource: candidateSource,
            targetPathHints: targetPathHints,
            experimentBudget: experimentBudget,
            recommendedTestCommand: command,
            targetFile: targetFile,
            rankedFallbackPaths: rankedFallbackPaths,
            dominantLanguage: dominantLanguage,
            patchFileCountLimit: patchFileCountLimit,
            aaeCandidateID: aaeCandidateID
        )
    }
    
    // MARK: - Phase 3: Convenience method for setting target path hints
    
    /// Returns a new TaskContext with target file path hints set
    public func withTargetPathHints(
        targetFile: String?,
        rankedFallbackPaths: [String]? = nil,
        dominantLanguage: String? = nil,
        patchFileCountLimit: Int? = nil
    ) -> TaskContext {
        TaskContext(
            goal: goal,
            agentKind: agentKind,
            workspaceRoot: workspaceRoot,
            phases: phases,
            projectMemoryRoot: projectMemoryRoot,
            experimentsRoot: experimentsRoot,
            maxExperimentCandidates: maxExperimentCandidates,
            experimentCandidates: experimentCandidates,
            plannerPreferredPath: plannerPreferredPath ?? targetFile,
            selectedCandidateID: selectedCandidateID,
            candidateSource: candidateSource,
            targetPathHints: targetFile.map { [$0] } ?? targetPathHints,
            experimentBudget: experimentBudget,
            recommendedTestCommand: recommendedTestCommand,
            targetFile: targetFile,
            rankedFallbackPaths: rankedFallbackPaths,
            dominantLanguage: dominantLanguage,
            patchFileCountLimit: patchFileCountLimit,
            aaeCandidateID: aaeCandidateID
        )
    }

    public static func from(
        goal: Goal,
        workspaceRoot: URL? = nil
    ) -> TaskContext {
        let agentKind = GoalClassifier.classify(
            description: goal.description,
            workspaceRoot: workspaceRoot
        )
        let phases: [TaskStepPhase] = switch agentKind {
        case .os:
            [.operatingSystem]
        case .code:
            [.engineering]
        case .mixed:
            [.handoff, .engineering]
        }

        return TaskContext(
            goal: goal,
            agentKind: agentKind,
            workspaceRoot: workspaceRoot?.path,
            phases: phases,
            projectMemoryRoot: workspaceRoot?.appendingPathComponent("ProjectMemory", isDirectory: true).path,
            experimentsRoot: workspaceRoot?.appendingPathComponent(".oracle/experiments", isDirectory: true).path,
            maxExperimentCandidates: 3,
            experimentCandidates: Array((goal.experimentCandidates ?? []).prefix(3)),
            plannerPreferredPath: goal.experimentCandidates?.first?.workspaceRelativePath
        )
    }
}
