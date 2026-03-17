import Foundation

// MARK: - Plan Source Markers (Phase 2: Planning Authority Normalization)

/// Markers indicating the source of a plan in the Oracle-AAE fusion system.
/// Oracle remains the planner of record while AAE provides advisory candidates.
public enum PlanSource: String, Codable, Sendable, CaseIterable {
    /// Oracle's own strong plan (internal confidence-based decision)
    case oracleNative = "oracle_native"
    /// Graph-backed/workflow-backed plan from Oracle
    case oracleGraph = "oracle_graph"
    /// AAE advisory candidates (validated but advisory only)
    case aaeAdvised = "aae_advised"
    /// Combined Oracle + AAE hybrid plan
    case oracleAAEHybrid = "oracle_aae_hybrid"
    
    /// Returns true if this source indicates AAE involvement
    public var isAAEInvolved: Bool {
        switch self {
        case .aaeAdvised, .oracleAAEHybrid:
            return true
        case .oracleNative, .oracleGraph:
            return false
        }
    }
    
    /// Returns true if this is Oracle's native planning (not AAE advised)
    public var isOracleNative: Bool {
        switch self {
        case .oracleNative, .oracleGraph:
            return true
        case .aaeAdvised, .oracleAAEHybrid:
            return false
        }
    }
}

// MARK: - Fused Plan Scoring Components

/// Components for the fused plan scoring formula
public struct PlanScoreComponents: Sendable, Codable {
    /// Oracle's internal confidence-weighted score (0.0 - 1.0)
    public let oracleConfidenceWeightedScore: Double
    
    /// AAE's predicted score as a factor (0.0 - 1.0)
    public let aaePredictedScore: Double
    
    /// Bonus points when target path matches AAE suggestion (0.0 - 0.2)
    public let targetPathMatchBonus: Double
    
    /// Safety bonus for bounded mutations (0.0 - 0.15)
    public let safetyBonus: Double
    
    /// Penalty for ambiguous/unclear situations (0.0 - 0.3)
    public let ambiguityPenalty: Double
    
    /// The final fused score
    public let finalScore: Double
    
    public init(
        oracleConfidenceWeightedScore: Double = 0.0,
        aaePredictedScore: Double = 0.0,
        targetPathMatchBonus: Double = 0.0,
        safetyBonus: Double = 0.0,
        ambiguityPenalty: Double = 0.0
    ) {
        self.oracleConfidenceWeightedScore = oracleConfidenceWeightedScore
        self.aaePredictedScore = aaePredictedScore
        self.targetPathMatchBonus = targetPathMatchBonus
        self.safetyBonus = safetyBonus
        self.ambiguityPenalty = ambiguityPenalty
        
        // Final score formula:
        // final_score = oracle_confidence_weighted_score
        //             + aae_predicted_score_weighted
        //             + target_path_match_bonus
        //             + safety_bonus
        //             - ambiguity_penalty
        
        // Weight AAE's predicted score at 30% to maintain Oracle as planner of record
        let aaeWeighted = aaePredictedScore * 0.30
        
        self.finalScore = min(1.0, max(0.0,
            oracleConfidenceWeightedScore
            + aaeWeighted
            + targetPathMatchBonus
            + safetyBonus
            - ambiguityPenalty
        ))
    }
    
    /// Returns a breakdown of the scoring for observability
    public var scoreBreakdown: [String: Double] {
        [
            "oracle_confidence": oracleConfidenceWeightedScore,
            "aae_predicted": aaePredictedScore,
            "aae_weighted": aaePredictedScore * 0.30,
            "target_path_bonus": targetPathMatchBonus,
            "safety_bonus": safetyBonus,
            "ambiguity_penalty": ambiguityPenalty,
            "final_score": finalScore
        ]
    }
}

public enum PlannerSource: String, Codable, Sendable {
    case workflow
    case stableGraph = "stable_graph"
    case candidateGraph = "candidate_graph"
    case exploration
    case reasoning
    case llm
    case recovery
    case strategy
}

public enum PlannerExecutionMode: String, Codable, Sendable {
    case direct
    case experiment
}

public struct PlannerDecision: Sendable {
    public let agentKind: AgentKind
    public let skillName: String
    public let plannerFamily: PlannerFamily
    public let stepPhase: TaskStepPhase
    public let executionMode: PlannerExecutionMode
    public let actionContract: ActionContract
    public let source: PlannerSource
    public let workflowID: String?
    public let workflowStepID: String?
    public let pathEdgeIDs: [String]
    public let currentEdgeID: String?
    public let fallbackReason: String?
    public let graphSearchDiagnostics: GraphSearchDiagnostics?
    public let semanticQuery: ElementQuery?
    public let projectMemoryRefs: [ProjectMemoryRef]
    public let architectureFindings: [ArchitectureFinding]
    public let refactorProposalID: String?
    public let experimentSpec: ExperimentSpec?
    public let experimentDecision: ExperimentDecision?
    public let experimentCandidateID: String?
    public let experimentSandboxPath: String?
    public let selectedExperimentCandidate: Bool?
    public let experimentOutcome: String?
    public let knowledgeTier: KnowledgeTier
    public let notes: [String]
    public let planDiagnostics: PlanDiagnostics?
    public let promptDiagnostics: PromptDiagnostics?
    public let recoveryTagged: Bool
    public let recoveryStrategy: String?
    public let recoverySource: String?
    public let planSource: PlanSource?
    
    // MARK: - Phase 2: Planning Authority Normalization Fields
    
    /// The AAE candidate ID that was selected (if any)
    public let selectedCandidateID: String?
    
    /// The source of the selected candidate (aae_advised, etc.)
    public let candidateSource: PlanSource?
    
    /// Target path hints from AAE for observability
    public let targetPathHints: [String]
    
    /// Budget for experiments (if using AAE candidates in experiment mode)
    public let experimentBudget: Int?
    
    /// Recommended test command for validation
    public let recommendedTestCommand: String?
    
    /// The fused scoring components for this plan
    public let scoreComponents: PlanScoreComponents?

    public init(
        agentKind: AgentKind = .os,
        skillName: String? = nil,
        plannerFamily: PlannerFamily = .os,
        stepPhase: TaskStepPhase = .operatingSystem,
        executionMode: PlannerExecutionMode = .direct,
        actionContract: ActionContract,
        source: PlannerSource,
        workflowID: String? = nil,
        workflowStepID: String? = nil,
        pathEdgeIDs: [String] = [],
        currentEdgeID: String? = nil,
        fallbackReason: String? = nil,
        graphSearchDiagnostics: GraphSearchDiagnostics? = nil,
        semanticQuery: ElementQuery? = nil,
        projectMemoryRefs: [ProjectMemoryRef] = [],
        architectureFindings: [ArchitectureFinding] = [],
        refactorProposalID: String? = nil,
        experimentSpec: ExperimentSpec? = nil,
        experimentDecision: ExperimentDecision? = nil,
        experimentCandidateID: String? = nil,
        experimentSandboxPath: String? = nil,
        selectedExperimentCandidate: Bool? = nil,
        experimentOutcome: String? = nil,
        knowledgeTier: KnowledgeTier? = nil,
        notes: [String] = [],
        planDiagnostics: PlanDiagnostics? = nil,
        promptDiagnostics: PromptDiagnostics? = nil,
        recoveryTagged: Bool = false,
        recoveryStrategy: String? = nil,
        recoverySource: String? = nil,
        planSource: PlanSource? = nil,
        // MARK: - Phase 2 new parameters
        selectedCandidateID: String? = nil,
        candidateSource: PlanSource? = nil,
        targetPathHints: [String] = [],
        experimentBudget: Int? = nil,
        recommendedTestCommand: String? = nil,
        scoreComponents: PlanScoreComponents? = nil
    ) {
        self.agentKind = agentKind
        self.skillName = skillName ?? actionContract.skillName
        self.plannerFamily = plannerFamily
        self.stepPhase = stepPhase
        self.executionMode = executionMode
        self.actionContract = actionContract
        self.source = source
        self.workflowID = workflowID
        self.workflowStepID = workflowStepID
        self.pathEdgeIDs = pathEdgeIDs
        self.currentEdgeID = currentEdgeID
        self.fallbackReason = fallbackReason
        self.graphSearchDiagnostics = graphSearchDiagnostics
        self.semanticQuery = semanticQuery
        self.projectMemoryRefs = projectMemoryRefs
        self.architectureFindings = architectureFindings
        self.refactorProposalID = refactorProposalID
        self.experimentSpec = experimentSpec
        self.experimentDecision = experimentDecision
        self.experimentCandidateID = experimentCandidateID
        self.experimentSandboxPath = experimentSandboxPath
        self.selectedExperimentCandidate = selectedExperimentCandidate
        self.experimentOutcome = experimentOutcome
        self.knowledgeTier = knowledgeTier ?? (recoveryTagged ? .recovery : (source == .exploration ? .exploration : .candidate))
        self.notes = notes
        self.planDiagnostics = planDiagnostics
        self.promptDiagnostics = promptDiagnostics
        self.recoveryTagged = recoveryTagged
        self.recoveryStrategy = recoveryStrategy
        self.recoverySource = recoverySource
        self.planSource = planSource
        
        self.selectedCandidateID = selectedCandidateID
        self.candidateSource = candidateSource
        self.targetPathHints = targetPathHints
        self.experimentBudget = experimentBudget
        self.recommendedTestCommand = recommendedTestCommand
        self.scoreComponents = scoreComponents
    }

    public func with(promptDiagnostics: PromptDiagnostics?) -> PlannerDecision {
        PlannerDecision(
            agentKind: agentKind,
            skillName: skillName,
            plannerFamily: plannerFamily,
            stepPhase: stepPhase,
            executionMode: executionMode,
            actionContract: actionContract,
            source: source,
            workflowID: workflowID,
            workflowStepID: workflowStepID,
            pathEdgeIDs: pathEdgeIDs,
            currentEdgeID: currentEdgeID,
            fallbackReason: fallbackReason,
            graphSearchDiagnostics: graphSearchDiagnostics,
            semanticQuery: semanticQuery,
            projectMemoryRefs: projectMemoryRefs,
            architectureFindings: architectureFindings,
            refactorProposalID: refactorProposalID,
            experimentSpec: experimentSpec,
            experimentDecision: experimentDecision,
            experimentCandidateID: experimentCandidateID,
            experimentSandboxPath: experimentSandboxPath,
            selectedExperimentCandidate: selectedExperimentCandidate,
            experimentOutcome: experimentOutcome,
            knowledgeTier: knowledgeTier,
            notes: notes,
            planDiagnostics: planDiagnostics,
            promptDiagnostics: promptDiagnostics,
            recoveryTagged: recoveryTagged,
            recoveryStrategy: recoveryStrategy,
            recoverySource: recoverySource,
            planSource: planSource,
            //
            selectedCandidateID: selectedCandidateID,
            candidateSource: candidateSource,
            targetPathHints: targetPathHints,
            experimentBudget: experimentBudget,
            recommendedTestCommand: recommendedTestCommand,
            scoreComponents: scoreComponents
        )
    }



    public func updated(
        actionContract: ActionContract? = nil,
        source: PlannerSource? = nil,
        notes: [String]? = nil,
        fallbackReason: String? = nil,
        // MARK: - Phase 2 new parameters for updated()
        planSource: PlanSource? = nil,
        selectedCandidateID: String? = nil,
        candidateSource: PlanSource? = nil,
        targetPathHints: [String]? = nil,
        experimentBudget: Int? = nil,
        recommendedTestCommand: String? = nil,
        scoreComponents: PlanScoreComponents? = nil
    ) -> PlannerDecision {
        PlannerDecision(
            agentKind: agentKind,
            skillName: skillName,
            plannerFamily: plannerFamily,
            stepPhase: stepPhase,
            executionMode: executionMode,
            actionContract: actionContract ?? self.actionContract,
            source: source ?? self.source,
            workflowID: workflowID,
            workflowStepID: workflowStepID,
            pathEdgeIDs: pathEdgeIDs,
            currentEdgeID: currentEdgeID,
            fallbackReason: fallbackReason ?? self.fallbackReason,
            graphSearchDiagnostics: graphSearchDiagnostics,
            semanticQuery: semanticQuery,
            projectMemoryRefs: projectMemoryRefs,
            architectureFindings: architectureFindings,
            refactorProposalID: refactorProposalID,
            experimentSpec: experimentSpec,
            experimentDecision: experimentDecision,
            experimentCandidateID: experimentCandidateID,
            experimentSandboxPath: experimentSandboxPath,
            selectedExperimentCandidate: selectedExperimentCandidate,
            experimentOutcome: experimentOutcome,
            knowledgeTier: knowledgeTier,
            notes: notes ?? self.notes,
            planDiagnostics: planDiagnostics,
            promptDiagnostics: promptDiagnostics,
            recoveryTagged: recoveryTagged,
            recoveryStrategy: recoveryStrategy,
            recoverySource: recoverySource,
            // MARK: - Phase 2 fields
            planSource: planSource ?? self.planSource,
            selectedCandidateID: selectedCandidateID ?? self.selectedCandidateID,
            candidateSource: candidateSource ?? self.candidateSource,
            targetPathHints: targetPathHints ?? self.targetPathHints,
            experimentBudget: experimentBudget ?? self.experimentBudget,
            recommendedTestCommand: recommendedTestCommand ?? self.recommendedTestCommand,
            scoreComponents: scoreComponents ?? self.scoreComponents
        )
    }

    public func normalized(
        fallbackReason: String? = nil,
        notes: [String]? = nil,
        // MARK: - Phase 2 new parameters for normalized()
        planSource: PlanSource? = nil,
        selectedCandidateID: String? = nil,
        candidateSource: PlanSource? = nil,
        targetPathHints: [String]? = nil,
        experimentBudget: Int? = nil,
        recommendedTestCommand: String? = nil,
        scoreComponents: PlanScoreComponents? = nil
    ) -> PlannerDecision {
        PlannerDecision(
            agentKind: agentKind,
            skillName: skillName,
            plannerFamily: plannerFamily,
            stepPhase: stepPhase,
            executionMode: executionMode,
            actionContract: actionContract,
            source: source,
            workflowID: workflowID,
            workflowStepID: workflowStepID,
            pathEdgeIDs: pathEdgeIDs,
            currentEdgeID: currentEdgeID,
            fallbackReason: fallbackReason ?? self.fallbackReason,
            graphSearchDiagnostics: graphSearchDiagnostics,
            semanticQuery: semanticQuery,
            projectMemoryRefs: projectMemoryRefs,
            architectureFindings: architectureFindings,
            refactorProposalID: refactorProposalID,
            experimentSpec: experimentSpec,
            experimentDecision: experimentDecision,
            experimentCandidateID: experimentCandidateID,
            experimentSandboxPath: experimentSandboxPath,
            selectedExperimentCandidate: selectedExperimentCandidate,
            experimentOutcome: experimentOutcome,
            knowledgeTier: knowledgeTier,
            notes: notes ?? self.notes,
            planDiagnostics: planDiagnostics,
            promptDiagnostics: promptDiagnostics,
            recoveryTagged: recoveryTagged,
            recoveryStrategy: recoveryStrategy,
            recoverySource: recoverySource,
            // MARK: - Phase 2 fields
            planSource: planSource ?? self.planSource,
            selectedCandidateID: selectedCandidateID ?? self.selectedCandidateID,
            candidateSource: candidateSource ?? self.candidateSource,
            targetPathHints: targetPathHints ?? self.targetPathHints,
            experimentBudget: experimentBudget ?? self.experimentBudget,
            recommendedTestCommand: recommendedTestCommand ?? self.recommendedTestCommand,
            scoreComponents: scoreComponents ?? self.scoreComponents
        )
    }
}
