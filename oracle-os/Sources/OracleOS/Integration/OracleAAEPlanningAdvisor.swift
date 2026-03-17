import Foundation

// MARK: - Phase 5: Bounded Experiment Loop

/// Budget tracking for experiment execution
public struct ExperimentBudget: Sendable, Codable {
    public let goalID: String
    public var candidatesRemaining: Int
    public var attemptsRemaining: Int
    public var failedAttempts: Int
    public var totalRuntimeSeconds: Int
    public var startTime: Date
    public var maxFailedAttempts: Int
    public var maxRuntimeSeconds: Int
    
    public init(
        goalID: String,
        maxCandidates: Int,
        maxAttempts: Int,
        maxRuntimeSeconds: Int,
        maxFailedAttempts: Int = 2
    ) {
        self.goalID = goalID
        self.candidatesRemaining = maxCandidates
        self.attemptsRemaining = maxAttempts
        self.failedAttempts = 0
        self.totalRuntimeSeconds = 0
        self.startTime = Date()
        self.maxFailedAttempts = maxFailedAttempts
        self.maxRuntimeSeconds = maxRuntimeSeconds
    }
    
    public var elapsedSeconds: Int {
        Int(Date().timeIntervalSince(startTime))
    }
    
    public var hasTimeRemaining: Bool {
        totalRuntimeSeconds + elapsedSeconds <= maxRuntimeSeconds
    }
    
    public var isExhausted: Bool {
        candidatesRemaining <= 0 || attemptsRemaining <= 0 || failedAttempts >= maxFailedAttempts
    }
}

/// Outcome of an experiment attempt
public enum AAEExperimentOutcome: Sendable, Codable {
    case success
    case partialSuccess
    case failure(reason: String)
    case timeout
    case aborted
    
    public var isSuccess: Bool {
        switch self {
        case .success, .partialSuccess:
            return true
        default:
            return false
        }
    }
}

/// Record of a single experiment attempt
public struct AAEExperimentAttempt: Sendable, Codable {
    public let goalID: String
    public let candidateID: String
    public let attemptNumber: Int
    public let outcome: AAEExperimentOutcome
    public let durationSeconds: Int
    public let timestamp: Date
    
    public init(
        goalID: String,
        candidateID: String,
        attemptNumber: Int,
        outcome: AAEExperimentOutcome,
        durationSeconds: Int
    ) {
        self.goalID = goalID
        self.candidateID = candidateID
        self.attemptNumber = attemptNumber
        self.outcome = outcome
        self.durationSeconds = durationSeconds
        self.timestamp = Date()
    }
}

// MARK: - Phase 2: Planning Authority Normalization

/// Candidate rejection reason tracking for observability
public struct CandidateRejectionRecord: Sendable, Codable {
    public let candidateId: String
    public let reason: String
    public let timestamp: Date
    
    public init(candidateId: String, reason: String, timestamp: Date = Date()) {
        self.candidateId = candidateId
        self.reason = reason
        self.timestamp = timestamp
    }
}

/// Scoring breakdown for observability
public struct CandidateScoreBreakdown: Sendable, Codable {
    public let candidateId: String
    public let oracleConfidenceScore: Double
    public let aaePredictedScore: Double
    public let targetPathMatchBonus: Double
    public let safetyBonus: Double
    public let ambiguityPenalty: Double
    public let finalScore: Double
    
    public init(
        candidateId: String,
        oracleConfidenceScore: Double,
        aaePredictedScore: Double,
        targetPathMatchBonus: Double = 0.0,
        safetyBonus: Double = 0.0,
        ambiguityPenalty: Double = 0.0
    ) {
        self.candidateId = candidateId
        self.oracleConfidenceScore = oracleConfidenceScore
        self.aaePredictedScore = aaePredictedScore
        self.targetPathMatchBonus = targetPathMatchBonus
        self.safetyBonus = safetyBonus
        self.ambiguityPenalty = ambiguityPenalty
        
        // Use PlanScoreComponents for final score calculation
        let components = PlanScoreComponents(
            oracleConfidenceWeightedScore: oracleConfidenceScore,
            aaePredictedScore: aaePredictedScore,
            targetPathMatchBonus: targetPathMatchBonus,
            safetyBonus: safetyBonus,
            ambiguityPenalty: ambiguityPenalty
        )
        self.finalScore = components.finalScore
    }
    
    public var breakdown: [String: Double] {
        [
            "candidate_id_hash": Double(candidateId.hashValue) / Double(Int.max),
            "oracle_confidence": oracleConfidenceScore,
            "aae_predicted": aaePredictedScore,
            "target_path_bonus": targetPathMatchBonus,
            "safety_bonus": safetyBonus,
            "ambiguity_penalty": ambiguityPenalty,
            "final_score": finalScore
        ]
    }
}

public actor OracleAAEPlanningAdvisor {
    private struct CacheKey: Hashable {
        let objective: String
        let workspaceRoot: String?
        let repositorySnapshotID: String?
        let recentFailureCount: Int
        let localSkillName: String?
    }

    private let client: OracleAAEBridgeClient
    private let validator: OracleAAECandidateValidator
    private let minimumOverrideScore: Double
    private var cache: [CacheKey: OracleAAEPlanResponse] = [:]
    
    // MARK: - Phase 5: Budget Tracking
    
    /// Budgets per goal for bounded experiment loop
    private var goalBudgets: [String: ExperimentBudget] = [:]
    
    /// History of all experiment attempts
    private var experimentHistory: [AAEExperimentAttempt] = []
    
    /// Configuration for budget limits
    private let maxCandidatesPerGoal: Int
    private let maxExecutionAttempts: Int
    private let maxTotalRuntimeSeconds: Int
    private let maxFailedAttemptsBeforeAbort: Int
    
    // MARK: - Phase 2: Candidate Tracking
    
    /// Track all candidate rejections for observability
    private var candidateRejections: [CandidateRejectionRecord] = []
    
    /// Track scoring breakdowns for all candidates
    private var candidateScoreBreakdowns: [CandidateScoreBreakdown] = []

    public init(
        client: OracleAAEBridgeClient,
        validator: OracleAAECandidateValidator? = nil,
        minimumOverrideScore: Double = 0.72,
        maxCandidatesPerGoal: Int = 5,
        maxExecutionAttempts: Int = 3,
        maxTotalRuntimeSeconds: Int = 300,
        maxFailedAttemptsBeforeAbort: Int = 2
    ) {
        self.client = client
        self.validator = validator ?? OracleAAECandidateValidator()
        self.minimumOverrideScore = minimumOverrideScore
        self.maxCandidatesPerGoal = maxCandidatesPerGoal
        self.maxExecutionAttempts = maxExecutionAttempts
        self.maxTotalRuntimeSeconds = maxTotalRuntimeSeconds
        self.maxFailedAttemptsBeforeAbort = maxFailedAttemptsBeforeAbort
    }

    public static func loadFromEnvironment(
        _ environment: [String: String] = ProcessInfo.processInfo.environment
    ) -> OracleAAEPlanningAdvisor? {
        guard let config = OracleAAEBridgeConfig.load(environment: environment) else {
            return nil
        }
        let threshold = Double(environment["ORACLE_AAE_MIN_OVERRIDE_SCORE"] ?? "") ?? 0.72
        return OracleAAEPlanningAdvisor(
            client: OracleAAEBridgeClient(config: config),
            minimumOverrideScore: threshold,
            maxCandidatesPerGoal: config.maxCandidatesPerGoal,
            maxExecutionAttempts: config.maxExecutionAttempts,
            maxTotalRuntimeSeconds: config.maxTotalRuntimeSeconds,
            maxFailedAttemptsBeforeAbort: config.maxFailedAttemptsBeforeAbort
        )
    }

    public func chooseDecision(
        goal: Goal,
        taskContext: TaskContext,
        worldState: WorldState,
        localDecision: PlannerDecision?,
        stepIndex: Int,
        recentFailureCount: Int
    ) async -> PlannerDecision? {
        guard taskContext.agentKind == .code || taskContext.agentKind == .mixed else {
            return localDecision
        }

        let cacheKey = CacheKey(
            objective: goal.description,
            workspaceRoot: taskContext.workspaceRoot ?? goal.workspaceRoot,
            repositorySnapshotID: worldState.repositorySnapshot?.id,
            recentFailureCount: recentFailureCount,
            localSkillName: localDecision?.skillName
        )

        let response: OracleAAEPlanResponse
        do {
            if let cached = cache[cacheKey] {
                response = cached
            } else {
                response = try await client.plan(
                    goalID: cacheKey.repositorySnapshotID ?? goal.description,
                    objective: goal.description,
                    repoPath: cacheKey.workspaceRoot,
                    stateSummary: makeStateSummary(
                        worldState: worldState,
                        localDecision: localDecision,
                        stepIndex: stepIndex,
                        recentFailureCount: recentFailureCount
                    ),
                    constraints: [
                        "agent_kind": taskContext.agentKind.rawValue,
                        "step_index": String(stepIndex),
                        "recent_failure_count": String(recentFailureCount),
                    ],
                    maxCandidates: 5
                )
                cache[cacheKey] = response
            }
        } catch {
            guard let localDecision else { return nil }
            return localDecision.normalized(
                notes: localDecision.notes + ["AAE advisory unavailable: \(String(describing: error))"]
            )
        }

        // Validate incoming candidates using the strict boundary validator
        let validationReport = await validator.validateCandidates(response.candidates)
        
        // Track validation failures for observability
        if !validationReport.allRejectionReasons.isEmpty {
            // Record rejection reasons
            for (candidateId, result) in validationReport.validationResults {
                if !result.isValid {
                    let reason = result.rejectionReason ?? "unknown"
                    candidateRejections.append(CandidateRejectionRecord(
                        candidateId: candidateId,
                        reason: reason
                    ))
                }
            }
            
            let validationNotes = [
                "AAE validation: \(validationReport.rejectedCandidates) candidates rejected",
                "AAE validation reasons: \(validationReport.allRejectionReasons.joined(separator: "; "))"
            ]
            
            // Add warnings to response for downstream processing
            var updatedResponse = response
            updatedResponse.warnings.append(contentsOf: validationReport.allRejectionReasons.map { "Validation: \($0)" })
            
            // If all candidates were rejected, return local decision
            guard validationReport.validCandidates > 0 else {
                guard let localDecision else { return nil }
                return localDecision.normalized(
                    notes: localDecision.notes + validationNotes + ["All AAE candidates rejected - using local decision"]
                )
            }
            
            // Continue with validated candidates
            guard let remoteDecision = mappedDecision(
                from: updatedResponse,
                validationReport: validationReport,
                taskContext: taskContext,
                localDecision: localDecision
            ) else {
                guard let localDecision else { return nil }
                return localDecision.normalized(
                    notes: localDecision.notes + validationNotes + ["AAE advisory returned no supported candidate"]
                )
            }

            // Flag requires_approval candidates
            if validationReport.requiresApprovalCount > 0 {
                let approvalNotes = [
                    "WARNING: \(validationReport.requiresApprovalCount) candidates require operator approval",
                    "Approved candidate IDs: \(validationReport.validationResults.filter { $0.value.requiresApprovalCandidates.isEmpty == false }.map { $0.key })"
                ]
                
                return remoteDecision.normalized(
                    notes: remoteDecision.notes + validationNotes + approvalNotes + response.warnings
                )
            }
            
            return remoteDecision.normalized(
                notes: remoteDecision.notes + validationNotes + response.warnings
            )
        }

        guard let remoteDecision = mappedDecision(
            from: response,
            validationReport: validationReport,
            taskContext: taskContext,
            localDecision: localDecision
        ) else {
            guard let localDecision else { return nil }
            return localDecision.normalized(
                notes: localDecision.notes + ["AAE advisory returned no supported candidate"] + response.warnings
            )
        }

        guard let localDecision else {
            return remoteDecision.normalized(
                notes: remoteDecision.notes + ["AAE selected the initial code step"] + response.warnings
            )
        }

        if shouldPreserveLocal(localDecision, remoteDecision: remoteDecision) {
            let preserved = mergePreferredPathIfAvailable(localDecision, remoteDecision: remoteDecision)
            return preserved.normalized(
                notes: preserved.notes + [
                    "AAE also evaluated the goal but Oracle kept the local \(localDecision.source.rawValue) plan"
                ] + response.warnings
            )
        }

        return remoteDecision.normalized(
            fallbackReason: localDecision.fallbackReason ?? remoteDecision.fallbackReason,
            notes: remoteDecision.notes + [
                "Oracle local planner suggested \(localDecision.skillName) from \(localDecision.source.rawValue)"
            ] + response.warnings
        )
    }
    
    // MARK: - Phase 5: Budget Management Methods
    
    /// Initialize or get existing budget for a goal
    public func getOrCreateBudget(for goalID: String) -> ExperimentBudget {
        if let existing = goalBudgets[goalID] {
            return existing
        }
        let budget = ExperimentBudget(
            goalID: goalID,
            maxCandidates: maxCandidatesPerGoal,
            maxAttempts: maxExecutionAttempts,
            maxRuntimeSeconds: maxTotalRuntimeSeconds,
            maxFailedAttempts: maxFailedAttemptsBeforeAbort
        )
        goalBudgets[goalID] = budget
        return budget
    }
    
    /// Get remaining budget for a goal
    public func getRemainingBudget(for goalID: String) -> ExperimentBudget? {
        goalBudgets[goalID]
    }
    
    /// Check if more attempts are allowed for a goal
    public func canAttemptMore(goalID: String) -> Bool {
        guard let budget = goalBudgets[goalID] else {
            return true // No budget yet, allow first attempt
        }
        return !budget.isExhausted && budget.hasTimeRemaining
    }
    
    /// Record an experiment attempt and update budget
    public func recordAttempt(goalID: String, candidateID: String, outcome: AAEExperimentOutcome, durationSeconds: Int) {
        // Create or get budget
        var budget = getOrCreateBudget(for: goalID)
        
        // Record the attempt
        let attempt = AAEExperimentAttempt(
            goalID: goalID,
            candidateID: candidateID,
            attemptNumber: budget.attemptsRemaining,
            outcome: outcome,
            durationSeconds: durationSeconds
        )
        experimentHistory.append(attempt)
        
        // Update budget based on outcome
        budget.attemptsRemaining -= 1
        budget.totalRuntimeSeconds += durationSeconds
        
        if !outcome.isSuccess {
            budget.failedAttempts += 1
        } else {
            budget.candidatesRemaining -= 1
        }
        
        goalBudgets[goalID] = budget
    }
    
    /// Get experiment history for a goal
    public func getExperimentHistory(for goalID: String) -> [AAEExperimentAttempt] {
        experimentHistory.filter { $0.goalID == goalID }
    }
    
    /// Clear budget for a goal (when goal is completed)
    public func clearBudget(for goalID: String) {
        goalBudgets.removeValue(forKey: goalID)
    }
    
    /// Get best successful attempt for a goal
    public func getBestAttempt(for goalID: String) -> AAEExperimentAttempt? {
        experimentHistory
            .filter { $0.goalID == goalID && $0.outcome.isSuccess }
            .sorted { $0.durationSeconds < $1.durationSeconds }
            .first
    }
    
    // MARK: - Phase 5: Bounded Experiment Loop Controller
    
    /// Result of bounded loop execution
    public struct BoundedLoopResult: Sendable {
        public let success: Bool
        public let bestCandidateID: String?
        public let totalAttempts: Int
        public let finalBudget: ExperimentBudget
        public let abortReason: String?
        
        public init(
            success: Bool,
            bestCandidateID: String?,
            totalAttempts: Int,
            finalBudget: ExperimentBudget,
            abortReason: String?
        ) {
            self.success = success
            self.bestCandidateID = bestCandidateID
            self.totalAttempts = totalAttempts
            self.finalBudget = finalBudget
            self.abortReason = abortReason
        }
    }
    
    /// Execute bounded experiment loop for code-repair or repo-refactor goals
    /// - Parameters:
    ///   - goalID: Unique identifier for the goal
    ///   - goalDescription: Description of the goal objective
    ///   - executeCandidate: Closure to execute a candidate and return outcome
    /// - Returns: BoundedLoopResult with the best result
    public func executeBoundedLoop(
        goalID: String,
        goalDescription: String,
        maxCandidates: Int? = nil,
        executeCandidate: @escaping (String) async -> AAEExperimentOutcome
    ) async -> BoundedLoopResult {
        let effectiveMaxCandidates = maxCandidates ?? maxCandidatesPerGoal
        
        // Get or create budget for this goal
        var budget = getOrCreateBudget(for: goalID)
        
        // Track best successful candidate
        var bestCandidateID: String?
        var bestOutcome: AAEExperimentOutcome?
        var totalAttempts = 0
        
        // Loop through candidates until budget exhausted or success
        for candidateIndex in 0..<effectiveMaxCandidates {
            // Check budget before each attempt
            guard canAttemptMore(goalID: goalID) else {
                return BoundedLoopResult(
                    success: bestOutcome?.isSuccess ?? false,
                    bestCandidateID: bestCandidateID,
                    totalAttempts: totalAttempts,
                    finalBudget: budget,
                    abortReason: "Budget exhausted: candidates=\(budget.candidatesRemaining), attempts=\(budget.attemptsRemaining), failed=\(budget.failedAttempts)"
                )
            }
            
            let candidateID = "\(goalID)-candidate-\(candidateIndex)"
            let startTime = Date()
            
            // Execute candidate
            let outcome = await executeCandidate(candidateID)
            let duration = Int(Date().timeIntervalSince(startTime))
            
            totalAttempts += 1
            
            // Record attempt in budget
            await recordAttempt(
                goalID: goalID,
                candidateID: candidateID,
                outcome: outcome,
                durationSeconds: duration
            )
            
            // Update best if successful
            if outcome.isSuccess {
                bestCandidateID = candidateID
                bestOutcome = outcome
                
                // Success - can stop early
                if case .success = outcome {
                    budget = getRemainingBudget(for: goalID) ?? budget
                    return BoundedLoopResult(
                        success: true,
                        bestCandidateID: candidateID,
                        totalAttempts: totalAttempts,
                        finalBudget: budget,
                        abortReason: nil
                    )
                }
            }
            
            // Check if we should abort due to too many failures
            budget = getRemainingBudget(for: goalID) ?? budget
            if budget.failedAttempts >= maxFailedAttemptsBeforeAbort {
                return BoundedLoopResult(
                    success: false,
                    bestCandidateID: bestCandidateID,
                    totalAttempts: totalAttempts,
                    finalBudget: budget,
                    abortReason: "Max failed attempts reached: \(budget.failedAttempts) >= \(maxFailedAttemptsBeforeAbort)"
                )
            }
        }
        
        // All candidates exhausted
        budget = getRemainingBudget(for: goalID) ?? budget
        return BoundedLoopResult(
            success: bestOutcome?.isSuccess ?? false,
            bestCandidateID: bestCandidateID,
            totalAttempts: totalAttempts,
            finalBudget: budget,
            abortReason: "All \(effectiveMaxCandidates) candidates exhausted"
        )
    }
    
    /// Get budget status summary for a goal
    public func getBudgetStatus(for goalID: String) -> String? {
        guard let budget = goalBudgets[goalID] else {
            return nil
        }
        return """
        Budget Status for \(goalID):
        - Candidates Remaining: \(budget.candidatesRemaining)
        - Attempts Remaining: \(budget.attemptsRemaining)
        - Failed Attempts: \(budget.failedAttempts)/\(budget.maxFailedAttempts)
        - Elapsed Time: \(budget.elapsedSeconds)s / \(budget.maxRuntimeSeconds)s
        - Is Exhausted: \(budget.isExhausted)
        """
    }
    
    public func resetValidationMetrics() async {
        await validator.resetMetrics()
    }
    
    // MARK: - Phase 2: Candidate Tracking Accessors
    
    /// Get all recorded candidate rejection records
    public func getCandidateRejections() -> [CandidateRejectionRecord] {
        candidateRejections
    }
    
    /// Get all recorded score breakdowns
    public func getScoreBreakdowns() -> [CandidateScoreBreakdown] {
        candidateScoreBreakdowns
    }
    
    /// Clear all tracked candidate data
    public func clearCandidateTracking() {
        candidateRejections.removeAll()
        candidateScoreBreakdowns.removeAll()
    }

    // MARK: - Validation Metrics Access

    public func getValidationMetrics() async -> (totalValidated: Int, totalRejected: Int, totalRequiresApproval: Int, rejectionReasons: [String: Int]) {
        await validator.getMetrics()
    }

    // MARK: - Phase 2: Merge Scoring Logic
    
    /// Compute fused score for a candidate using the Phase 2 formula
    ///
    /// Formula:
    /// final_score = oracle_confidence_weighted_score
    ///             + aae_predicted_score_weighted
    ///             + target_path_match_bonus
    ///             + safety_bonus
    ///             - ambiguity_penalty
    private func computeFusedScore(
        candidate: OracleAAECandidate,
        localDecision: PlannerDecision?,
        targetPathMatches: Bool
    ) -> CandidateScoreBreakdown {
        // Oracle's internal confidence (derive from candidate confidence or use default)
        let oracleConfidenceScore = candidate.confidence * 0.70 + 0.20  // Scale to 0.2-0.9 range
        
        // AAE's predicted score
        let aaePredictedScore = candidate.predictedScore
        
        // Target path match bonus (0.0 - 0.2)
        let targetPathMatchBonus: Double = targetPathMatches ? 0.15 : 0.0
        
        // Safety bonus for bounded mutations (0.0 - 0.15)
        // Check if this is a safe operation (read-only or test)
        let isSafeOperation = candidate.kind.contains("inspect") || 
                             candidate.kind.contains("test") ||
                             candidate.kind.contains("validate")
        let safetyBonus: Double = isSafeOperation ? 0.10 : 0.0
        
        // Ambiguity penalty (0.0 - 0.3)
        // Penalize if objective is unclear or multiple interpretations
        let hasAmbiguity = candidate.rationale.contains("ambiguous") ||
                          candidate.rationale.contains("unclear") ||
                          candidate.rationale.contains("multiple")
        let ambiguityPenalty: Double = hasAmbiguity ? 0.20 : 0.0
        
        return CandidateScoreBreakdown(
            candidateId: candidate.candidateID,
            oracleConfidenceScore: oracleConfidenceScore,
            aaePredictedScore: aaePredictedScore,
            targetPathMatchBonus: targetPathMatchBonus,
            safetyBonus: safetyBonus,
            ambiguityPenalty: ambiguityPenalty
        )
    }
    
    /// Deterministic tie-breaking: lowest candidate_id wins
    private func deterministicTieBreak(_ candidates: [OracleAAECandidate]) -> [OracleAAECandidate] {
        candidates.sorted { a, b in
            if a.predictedScore == b.predictedScore {
                // Deterministic tie-break: lowest candidate_id wins (lexicographically)
                return a.candidateID < b.candidateID
            }
            return a.predictedScore > b.predictedScore
        }
    }

    private func shouldPreserveLocal(
        _ localDecision: PlannerDecision,
        remoteDecision: PlannerDecision
    ) -> Bool {
        if localDecision.source == .recovery {
            return true
        }
        if localDecision.source == .workflow || localDecision.source == .stableGraph || localDecision.source == .candidateGraph {
            return true
        }
        if localDecision.skillName == remoteDecision.skillName {
            return true
        }
        let remoteSpecificity = specificity(of: remoteDecision.skillName)
        let localSpecificity = specificity(of: localDecision.skillName)
        if remoteSpecificity > localSpecificity {
            return remoteDecision.actionContract.targetLabel == nil && remoteDecision.actionContract.workspaceRelativePath == nil
                ? true
                : false
        }
        return remoteDecision.planDiagnostics == nil && localDecision.source != .exploration
            ? true
            : false
    }

    private func specificity(of skillName: String) -> Int {
        switch skillName {
        case "read_repository":
            return 0
        case "search_code":
            return 1
        case "run_tests", "run_build":
            return 2
        case "edit_file", "generate_patch", "write_file":
            return 3
        default:
            return 0
        }
    }

    private func mergePreferredPathIfAvailable(
        _ localDecision: PlannerDecision,
        remoteDecision: PlannerDecision
    ) -> PlannerDecision {
        guard localDecision.skillName == remoteDecision.skillName,
              localDecision.actionContract.workspaceRelativePath == nil,
              let preferredPath = remoteDecision.actionContract.workspaceRelativePath
        else {
            return localDecision
        }

        let mergedContract = ActionContract(
            id: localDecision.actionContract.id + "|aae-path|" + preferredPath,
            agentKind: localDecision.actionContract.agentKind,
            domain: localDecision.actionContract.domain,
            skillName: localDecision.actionContract.skillName,
            targetRole: localDecision.actionContract.targetRole,
            targetLabel: localDecision.actionContract.targetLabel ?? remoteDecision.actionContract.targetLabel,
            locatorStrategy: localDecision.actionContract.locatorStrategy + "+aae",
            workspaceRelativePath: preferredPath,
            commandCategory: localDecision.actionContract.commandCategory,
            plannerFamily: localDecision.actionContract.plannerFamily
        )

        // MARK: - Phase 2: Include scoring components in merged decision
        let scoreComponents = PlanScoreComponents(
            oracleConfidenceWeightedScore: 0.6,
            aaePredictedScore: remoteDecision.scoreComponents?.aaePredictedScore ?? 0.5,
            targetPathMatchBonus: 0.15,
            safetyBonus: 0.0,
            ambiguityPenalty: 0.0
        )

        return localDecision.updated(
            actionContract: mergedContract,
            notes: localDecision.notes + ["AAE suggested target path \(preferredPath)"],
            // MARK: - Phase 2: Mark as hybrid plan
            planSource: .oracleAAEHybrid,
            selectedCandidateID: remoteDecision.selectedCandidateID,
            candidateSource: .oracleAAEHybrid,
            targetPathHints: remoteDecision.targetPathHints + [preferredPath],
            scoreComponents: scoreComponents
        )
    }

    private func mappedDecision(
        from response: OracleAAEPlanResponse,
        validationReport: OracleAAEValidationReport,
        taskContext: TaskContext,
        localDecision: PlannerDecision?
    ) -> PlannerDecision? {
        // Use validation report to filter only valid candidates
        let validCandidates = response.candidates.filter { candidate in
            guard let result = validationReport.validationResults[candidate.candidateID] else {
                return false
            }
            return result.isValid
        }

        // MARK: - Phase 2: Use deterministic tie-breaking
        let ranked = deterministicTieBreak(validCandidates)

        for candidate in ranked {
            guard candidate.predictedScore >= minimumOverrideScore || localDecision == nil else {
                continue
            }
            
            // MARK: - Phase 2: Compute fused score
            let targetPathMatches = candidate.payload.stringValue(forKey: "workspace_relative_path") != nil
            let scoreBreakdown = computeFusedScore(
                candidate: candidate,
                localDecision: localDecision,
                targetPathMatches: targetPathMatches
            )
            
            // Track scoring breakdown for observability
            candidateScoreBreakdowns.append(scoreBreakdown)
            
            guard let decision = decision(
                for: candidate, 
                response: response, 
                taskContext: taskContext,
                scoreBreakdown: scoreBreakdown
            ) else {
                continue
            }
            return decision
        }
        return nil
    }

    private func decision(
        for candidate: OracleAAECandidate,
        response: OracleAAEPlanResponse,
        taskContext: TaskContext,
        scoreBreakdown: CandidateScoreBreakdown? = nil
    ) -> PlannerDecision? {
        guard let skillName = mappedSkillName(for: candidate.kind) else {
            return nil
        }

        let workspaceRelativePath = candidate.payload.stringValue(forKey: "workspace_relative_path")
            ?? candidate.payload.stringArrayValue(forKey: "candidate_paths")?.first
        let commandCategory = mappedCommandCategory(for: skillName)
        
        // MARK: - Phase 2: Include scoring breakdown in notes
        var notes = [
            "AAE advisory selected \(candidate.kind)",
            "tool \(candidate.tool)",
            "predicted score \(String(format: "%.2f", candidate.predictedScore))",
            candidate.rationale,
        ]
        
        if let breakdown = scoreBreakdown {
            notes.append("fused score \(String(format: "%.3f", breakdown.finalScore))")
            notes.append("score breakdown: oracle_confidence=\(String(format: "%.2f", breakdown.oracleConfidenceScore)), aae_predicted=\(String(format: "%.2f", breakdown.aaePredictedScore)), target_path_bonus=\(String(format: "%.2f", breakdown.targetPathMatchBonus)), safety_bonus=\(String(format: "%.2f", breakdown.safetyBonus)), ambiguity_penalty=\(String(format: "%.2f", breakdown.ambiguityPenalty))")
        }
        
        let contract = ActionContract(
            id: ["code", "aae", candidate.kind, workspaceRelativePath ?? "none", candidate.candidateID].joined(separator: "|"),
            agentKind: .code,
            skillName: skillName,
            targetRole: nil,
            targetLabel: workspaceRelativePath ?? candidate.tool,
            locatorStrategy: "aae-bridge",
            workspaceRelativePath: workspaceRelativePath,
            commandCategory: commandCategory,
            plannerFamily: PlannerFamily.code.rawValue
        )
        
        // MARK: - Phase 2: Create score components
        let components = scoreBreakdown.map { breakdown in
            PlanScoreComponents(
                oracleConfidenceWeightedScore: breakdown.oracleConfidenceScore,
                aaePredictedScore: breakdown.aaePredictedScore,
                targetPathMatchBonus: breakdown.targetPathMatchBonus,
                safetyBonus: breakdown.safetyBonus,
                ambiguityPenalty: breakdown.ambiguityPenalty
            )
        }

        return PlannerDecision(
            agentKind: taskContext.agentKind == .mixed ? .mixed : .code,
            skillName: skillName,
            plannerFamily: .code,
            stepPhase: .engineering,
            executionMode: .direct,
            actionContract: contract,
            source: .reasoning,
            fallbackReason: "AAE oracle bridge supplied a ranked advisory step",
            notes: notes,
            // MARK: - Phase 2: Tag with source marker
            planSource: .aaeAdvised,
            selectedCandidateID: candidate.candidateID,
            candidateSource: .aaeAdvised,
            targetPathHints: workspaceRelativePath.map { [$0] } ?? [],
            recommendedTestCommand: candidate.payload.stringValue(forKey: "recommended_test_command"),
            scoreComponents: components
        )
    }

    private func mappedSkillName(for kind: String) -> String? {
        switch kind {
        case "aae.inspect_repository", "aae.analyze_objective":
            return "read_repository"
        case "aae.run_targeted_tests", "aae.validate_candidate":
            return "run_tests"
        case "aae.localize_failure", "aae.estimate_change_impact":
            return "search_code"
        case "aae.generate_patch":
            return "generate_patch"
        default:
            return nil
        }
    }

    private func mappedCommandCategory(for skillName: String) -> String? {
        switch skillName {
        case "read_repository":
            return CodeCommandCategory.indexRepository.rawValue
        case "search_code":
            return CodeCommandCategory.searchCode.rawValue
        case "generate_patch":
            return CodeCommandCategory.generatePatch.rawValue
        case "run_tests":
            return CodeCommandCategory.test.rawValue
        default:
            return nil
        }
    }

    private func makeStateSummary(
        worldState: WorldState,
        localDecision: PlannerDecision?,
        stepIndex: Int,
        recentFailureCount: Int
    ) -> String {
        var parts: [String] = [
            "step=\(stepIndex)",
            "recent_failures=\(recentFailureCount)",
        ]
        if let buildTool = worldState.repositorySnapshot?.buildTool.rawValue {
            parts.append("build_tool=\(buildTool)")
        }
        if let lastAction = worldState.lastAction?.action {
            parts.append("last_action=\(lastAction)")
        }
        if let localDecision {
            parts.append("local_skill=\(localDecision.skillName)")
            parts.append("local_source=\(localDecision.source.rawValue)")
        }
        if let app = worldState.observation.app {
            parts.append("app=\(app)")
        }
        return parts.joined(separator: "; ")
    }
}
