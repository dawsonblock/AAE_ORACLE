import Foundation

// MARK: - Experiment Outcome Models

/// Represents the outcome of an experiment execution for scoring
public struct ExperimentOutcome: Sendable, Codable {
    public let goalID: String
    public let candidateID: String
    public let commandExecuted: String
    public let touchedFiles: [String]
    public let testResults: TestResultSummary
    public let buildResults: BuildResultSummary
    public let runtimeDiagnostics: [String]
    public let domainEventSummary: String
    public let safetyViolations: [SafetyViolation]
    public let elapsedTimeSeconds: Double
    public let executionStatus: ExecutionStatus
    public let traceID: String?

    enum CodingKeys: String, CodingKey {
        case goalID = "goal_id"
        case candidateID = "candidate_id"
        case commandExecuted = "command_executed"
        case touchedFiles = "touched_files"
        case testResults = "test_results"
        case buildResults = "build_results"
        case runtimeDiagnostics = "runtime_diagnostics"
        case domainEventSummary = "domain_event_summary"
        case safetyViolations = "safety_violations"
        case elapsedTimeSeconds = "elapsed_time_seconds"
        case executionStatus = "execution_status"
        case traceID = "trace_id"
    }

    public init(
        goalID: String,
        candidateID: String,
        commandExecuted: String,
        touchedFiles: [String],
        testResults: TestResultSummary,
        buildResults: BuildResultSummary,
        runtimeDiagnostics: [String],
        domainEventSummary: String,
        safetyViolations: [SafetyViolation],
        elapsedTimeSeconds: Double,
        executionStatus: ExecutionStatus,
        traceID: String? = nil
    ) {
        self.goalID = goalID
        self.candidateID = candidateID
        self.commandExecuted = commandExecuted
        self.touchedFiles = touchedFiles
        self.testResults = testResults
        self.buildResults = buildResults
        self.runtimeDiagnostics = runtimeDiagnostics
        self.domainEventSummary = domainEventSummary
        self.safetyViolations = safetyViolations
        self.elapsedTimeSeconds = elapsedTimeSeconds
        self.executionStatus = executionStatus
        self.traceID = traceID
    }
}

/// Test result summary
public struct TestResultSummary: Sendable, Codable {
    public let passed: Int
    public let failed: Int
    public let skipped: Int
    public let errors: Int
    public let totalTests: Int

    enum CodingKeys: String, CodingKey {
        case passed
        case failed
        case skipped
        case errors
        case totalTests = "total_tests"
    }

    public init(passed: Int, failed: Int, skipped: Int, errors: Int, totalTests: Int) {
        self.passed = passed
        self.failed = failed
        self.skipped = skipped
        self.errors = errors
        self.totalTests = totalTests
    }

    public var isSuccess: Bool {
        return failed == 0 && errors == 0
    }
}

/// Build result summary
public struct BuildResultSummary: Sendable, Codable {
    public let success: Bool
    public let errorCount: Int
    public let warningCount: Int
    public let errorMessages: [String]

    enum CodingKeys: String, CodingKey {
        case success
        case errorCount = "error_count"
        case warningCount = "warning_count"
        case errorMessages = "error_messages"
    }

    public init(success: Bool, errorCount: Int, warningCount: Int, errorMessages: [String]) {
        self.success = success
        self.errorCount = errorCount
        self.warningCount = warningCount
        self.errorMessages = errorMessages
    }
}

/// Safety violation record
public struct SafetyViolation: Sendable, Codable {
    public let violationType: String
    public let severity: String
    public let description: String
    public let filePath: String?
    public let lineNumber: Int?

    enum CodingKeys: String, CodingKey {
        case violationType = "violation_type"
        case severity
        case description
        case filePath = "file_path"
        case lineNumber = "line_number"
    }

    public init(violationType: String, severity: String, description: String, filePath: String? = nil, lineNumber: Int? = nil) {
        self.violationType = violationType
        self.severity = severity
        self.description = description
        self.filePath = filePath
        self.lineNumber = lineNumber
    }
}

/// Execution status enum
public enum ExecutionStatus: String, Sendable, Codable {
    case success
    case partial
    case failure
}

/// Response from AAE after processing experiment result
public struct ExperimentResultResponse: Sendable, Codable {
    public let score: Double
    public let failureMode: String?
    public let repairUsefulness: String
    public let feedbackSummary: String
    public let updatedCandidateRanking: [CandidateRankingUpdate]?

    enum CodingKeys: String, CodingKey {
        case score
        case failureMode = "failure_mode"
        case repairUsefulness = "repair_usefulness"
        case feedbackSummary = "feedback_summary"
        case updatedCandidateRanking = "updated_candidate_ranking"
    }

    public init(
        score: Double,
        failureMode: String?,
        repairUsefulness: String,
        feedbackSummary: String,
        updatedCandidateRanking: [CandidateRankingUpdate]?
    ) {
        self.score = score
        self.failureMode = failureMode
        self.repairUsefulness = repairUsefulness
        self.feedbackSummary = feedbackSummary
        self.updatedCandidateRanking = updatedCandidateRanking
    }
}

/// Candidate ranking update from AAE
public struct CandidateRankingUpdate: Sendable, Codable {
    public let candidateID: String
    public let newScore: Double
    public let rankChange: Int

    enum CodingKeys: String, CodingKey {
        case candidateID = "candidate_id"
        case newScore = "new_score"
        case rankChange = "rank_change"
    }

    public init(candidateID: String, newScore: Double, rankChange: Int) {
        self.candidateID = candidateID
        self.newScore = newScore
        self.rankChange = rankChange
    }
}

// MARK: - Experiment Coordinator

public struct OracleAAEExperimentCoordinator: Sendable {
    private let client: OracleAAEBridgeClient

    public init(client: OracleAAEBridgeClient) {
        self.client = client
    }

    public func proposeCommands(
        goalID: String,
        intentID: UUID,
        objective: String,
        repoPath: String? = nil,
        stateSummary: String = "",
        constraints: [String: String] = [:],
        maxCandidates: Int = 5
    ) async throws -> [OracleAAECommand] {
        let response = try await client.plan(
            goalID: goalID,
            objective: objective,
            repoPath: repoPath,
            stateSummary: stateSummary,
            constraints: constraints,
            maxCandidates: maxCandidates
        )

        let payloadEncoder = JSONEncoder()
        payloadEncoder.outputFormatting = [.sortedKeys]

        return try response.candidates.map { candidate in
            let payloadData = try payloadEncoder.encode(candidate.payload)
            let payloadJSON = String(decoding: payloadData, as: UTF8.self)
            let metadata = CommandMetadata(
                intentID: intentID,
                planningStrategy: response.engine,
                rationale: candidate.rationale,
                confidence: candidate.confidence
            )
            return OracleAAECommand(
                kind: candidate.kind,
                metadata: metadata,
                candidateID: candidate.candidateID,
                tool: candidate.tool,
                payloadJSON: payloadJSON,
                safetyClass: candidate.safetyClass,
                predictedScore: candidate.predictedScore
            )
        }
    }

    /// Send experiment result back to AAE for scoring and ranking updates
    public func sendExperimentResult(_ outcome: ExperimentOutcome) async throws -> ExperimentResultResponse {
        return try await client.sendExperimentResult(outcome)
    }
}
