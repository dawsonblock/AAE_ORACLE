
import Foundation

public indirect enum OracleAAEJSONValue: Sendable, Codable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: OracleAAEJSONValue])
    case array([OracleAAEJSONValue])
    case null

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: OracleAAEJSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([OracleAAEJSONValue].self) {
            self = .array(value)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value")
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }
}



public extension OracleAAEJSONValue {
    var stringValue: String? {
        guard case .string(let value) = self else { return nil }
        return value
    }

    var numberValue: Double? {
        guard case .number(let value) = self else { return nil }
        return value
    }

    var boolValue: Bool? {
        guard case .bool(let value) = self else { return nil }
        return value
    }

    var objectValue: [String: OracleAAEJSONValue]? {
        guard case .object(let value) = self else { return nil }
        return value
    }

    var arrayValue: [OracleAAEJSONValue]? {
        guard case .array(let value) = self else { return nil }
        return value
    }
}

public extension Dictionary where Key == String, Value == OracleAAEJSONValue {
    func stringValue(forKey key: String) -> String? {
        self[key]?.stringValue
    }

    func stringArrayValue(forKey key: String) -> [String]? {
        self[key]?.arrayValue?.compactMap(\.stringValue)
    }
}

public struct OracleAAEPlanRequest: Sendable, Codable {
    public let goalID: String
    public let objective: String
    public let repoPath: String?
    public let stateSummary: String
    public let constraints: [String: String]
    public let maxCandidates: Int

    enum CodingKeys: String, CodingKey {
        case goalID = "goal_id"
        case objective
        case repoPath = "repo_path"
        case stateSummary = "state_summary"
        case constraints
        case maxCandidates = "max_candidates"
    }

    public init(
        goalID: String,
        objective: String,
        repoPath: String? = nil,
        stateSummary: String = "",
        constraints: [String: String] = [:],
        maxCandidates: Int = 5
    ) {
        self.goalID = goalID
        self.objective = objective
        self.repoPath = repoPath
        self.stateSummary = stateSummary
        self.constraints = constraints
        self.maxCandidates = max(1, maxCandidates)
    }
}

public struct OracleAAECandidate: Sendable, Codable {
    public let candidateID: String
    public let kind: String
    public let tool: String
    public let payload: [String: OracleAAEJSONValue]
    public let rationale: String
    public let confidence: Double
    public let predictedScore: Double
    public let safetyClass: String
    
    // MARK: - Phase 3: Target Path Hints
    /// Primary target file path suggested by AAE
    public let targetFile: String?
    
    /// Ranked array of alternative fallback paths
    public let rankedFallbackPaths: [String]?
    
    /// Suggested test command for validation
    public let recommendedTestCommand: String?
    
    /// Dominant programming language for the candidate
    public let dominantLanguage: String?
    
    /// Maximum number of files to modify for this patch
    public let patchFileCountLimit: Int?
    
    enum CodingKeys: String, CodingKey {
        case candidateID = "candidate_id"
        case kind
        case tool
        case payload
        case rationale
        case confidence
        case predictedScore = "predicted_score"
        case safetyClass = "safety_class"
        // Phase 3 keys
        case targetFile = "target_file"
        case rankedFallbackPaths = "ranked_fallback_paths"
        case recommendedTestCommand = "recommended_test_command"
        case dominantLanguage = "dominant_language"
        case patchFileCountLimit = "patch_file_count_limit"
    }

    public init(
        candidateID: String,
        kind: String,
        tool: String,
        payload: [String: OracleAAEJSONValue],
        rationale: String,
        confidence: Double,
        predictedScore: Double,
        safetyClass: String,
        targetFile: String? = nil,
        rankedFallbackPaths: [String]? = nil,
        recommendedTestCommand: String? = nil,
        dominantLanguage: String? = nil,
        patchFileCountLimit: Int? = nil
    ) {
        self.candidateID = candidateID
        self.kind = kind
        self.tool = tool
        self.payload = payload
        self.rationale = rationale
        self.confidence = confidence
        self.predictedScore = predictedScore
        self.safetyClass = safetyClass
        self.targetFile = targetFile
        self.rankedFallbackPaths = rankedFallbackPaths
        self.recommendedTestCommand = recommendedTestCommand
        self.dominantLanguage = dominantLanguage
        self.patchFileCountLimit = patchFileCountLimit
    }
}

public struct OracleAAEPlanResponse: Sendable, Codable {
    public let goalID: String
    public let engine: String
    public let summary: [String: OracleAAEJSONValue]
    public let warnings: [String]
    public let candidates: [OracleAAECandidate]

    enum CodingKeys: String, CodingKey {
        case goalID = "goal_id"
        case engine
        case summary
        case warnings
        case candidates
    }

    public init(goalID: String, engine: String, summary: [String: OracleAAEJSONValue], warnings: [String], candidates: [OracleAAECandidate]) {
        self.goalID = goalID
        self.engine = engine
        self.summary = summary
        self.warnings = warnings
        self.candidates = candidates
    }
}

public struct OracleAAECommand: Command, Sendable, Codable {
    public let id: CommandID
    public let kind: String
    public let metadata: CommandMetadata
    public let candidateID: String
    public let tool: String
    public let payloadJSON: String
    public let safetyClass: String
    public let predictedScore: Double

    public init(
        id: CommandID = CommandID(),
        kind: String,
        metadata: CommandMetadata,
        candidateID: String,
        tool: String,
        payloadJSON: String,
        safetyClass: String,
        predictedScore: Double
    ) {
        self.id = id
        self.kind = kind
        self.metadata = metadata
        self.candidateID = candidateID
        self.tool = tool
        self.payloadJSON = payloadJSON
        self.safetyClass = safetyClass
        self.predictedScore = predictedScore
    }
}
