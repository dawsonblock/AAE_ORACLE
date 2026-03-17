import Foundation

public struct OracleAAEBridgeConfig: Sendable, Codable {
    public let baseURL: URL
    public let planEndpoint: String
    public let resultEndpoint: String
    public let timeoutSeconds: TimeInterval
    
    // MARK: - Phase 5: Budget Controls
    
    /// Maximum number of candidates to request per goal
    public let maxCandidatesPerGoal: Int
    
    /// Maximum number of execution attempts per candidate
    public let maxExecutionAttempts: Int
    
    /// Maximum number of patch files to generate per attempt
    public let maxPatchFiles: Int
    
    /// Maximum total runtime in seconds for the experiment loop
    public let maxTotalRuntimeSeconds: Int
    
    /// Maximum number of failed attempts before aborting the experiment
    public let maxFailedAttemptsBeforeAbort: Int
    
    public let enabled: Bool

    enum CodingKeys: String, CodingKey {
        case baseURL = "base_url"
        case planEndpoint = "plan_endpoint"
        case resultEndpoint = "result_endpoint"
        case timeoutSeconds = "timeout_seconds"
        case maxCandidatesPerGoal = "max_candidates_per_goal"
        case maxExecutionAttempts = "max_execution_attempts"
        case maxPatchFiles = "max_patch_files"
        case maxTotalRuntimeSeconds = "max_total_runtime_seconds"
        case maxFailedAttemptsBeforeAbort = "max_failed_attempts_before_abort"
        case enabled
    }

    public init(
        baseURL: URL,
        planEndpoint: String = "/api/oracle/plan",
        resultEndpoint: String = "/api/oracle/experiment_result",
        timeoutSeconds: TimeInterval = 30,
        maxCandidatesPerGoal: Int = 5,
        maxExecutionAttempts: Int = 3,
        maxPatchFiles: Int = 3,
        maxTotalRuntimeSeconds: Int = 300,
        maxFailedAttemptsBeforeAbort: Int = 2,
        enabled: Bool = true
    ) {
        self.baseURL = baseURL
        self.planEndpoint = planEndpoint
        self.resultEndpoint = resultEndpoint
        self.timeoutSeconds = timeoutSeconds
        self.maxCandidatesPerGoal = maxCandidatesPerGoal
        self.maxExecutionAttempts = maxExecutionAttempts
        self.maxPatchFiles = maxPatchFiles
        self.maxTotalRuntimeSeconds = maxTotalRuntimeSeconds
        self.maxFailedAttemptsBeforeAbort = maxFailedAttemptsBeforeAbort
        self.enabled = enabled
    }
    
    // MARK: - Backward Compatibility
    
    /// Alias for maxCandidatesPerGoal - kept for backward compatibility
    public var defaultMaxCandidates: Int {
        maxCandidatesPerGoal
    }

    public var planURL: URL {
        if let url = URL(string: planEndpoint, relativeTo: baseURL) {
            return url
        }
        return baseURL
    }

    public var resultURL: URL {
        if let url = URL(string: resultEndpoint, relativeTo: baseURL) {
            return url
        }
        return baseURL
    }

    public static func load(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        fileManager: FileManager = .default
    ) -> OracleAAEBridgeConfig? {
        if let rawEnabled = environment["ORACLE_AAE_ENABLED"], Self.parseBool(rawEnabled) == false {
            return nil
        }

        if let explicitPath = environment["ORACLE_AAE_CONFIG"],
           let config = Self.loadJSON(url: URL(fileURLWithPath: explicitPath, isDirectory: false)) {
            return config.enabled ? config : nil
        }

        let defaultConfigURL = URL(fileURLWithPath: fileManager.currentDirectoryPath, isDirectory: true)
            .appendingPathComponent("configs", isDirectory: true)
            .appendingPathComponent("oracle_aae_bridge.json", isDirectory: false)
        if fileManager.fileExists(atPath: defaultConfigURL.path),
           let config = Self.loadJSON(url: defaultConfigURL) {
            return config.enabled ? config : nil
        }

        guard let baseURLString = environment["ORACLE_AAE_BASE_URL"],
              let baseURL = URL(string: baseURLString)
        else {
            return nil
        }

        return OracleAAEBridgeConfig(
            baseURL: baseURL,
            planEndpoint: environment["ORACLE_AAE_PLAN_ENDPOINT"] ?? "/api/oracle/plan",
            resultEndpoint: environment["ORACLE_AAE_RESULT_ENDPOINT"] ?? "/api/oracle/experiment_result",
            timeoutSeconds: Double(environment["ORACLE_AAE_TIMEOUT_SECONDS"] ?? "") ?? 30,
            maxCandidatesPerGoal: Int(environment["ORACLE_AAE_MAX_CANDIDATES"] ?? "") ?? 5,
            maxExecutionAttempts: Int(environment["ORACLE_AAE_MAX_EXECUTION_ATTEMPTS"] ?? "") ?? 3,
            maxPatchFiles: Int(environment["ORACLE_AAE_MAX_PATCH_FILES"] ?? "") ?? 3,
            maxTotalRuntimeSeconds: Int(environment["ORACLE_AAE_MAX_TOTAL_RUNTIME"] ?? "") ?? 300,
            maxFailedAttemptsBeforeAbort: Int(environment["ORACLE_AAE_MAX_FAILED_ATTEMPTS"] ?? "") ?? 2,
            enabled: environment["ORACLE_AAE_ENABLED"].map(Self.parseBool) ?? true
        )
    }

    private static func loadJSON(url: URL) -> OracleAAEBridgeConfig? {
        guard let data = try? Data(contentsOf: url) else {
            return nil
        }
        let decoder = JSONDecoder()
        return try? decoder.decode(OracleAAEBridgeConfig.self, from: data)
    }

    private static func parseBool(_ raw: String) -> Bool {
        switch raw.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
        case "1", "true", "yes", "on":
            return true
        case "0", "false", "no", "off":
            return false
        default:
            return false
        }
    }
}
