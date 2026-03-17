import Foundation

public actor OracleAAEBridgeClient {
    private let config: OracleAAEBridgeConfig
    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    public init(config: OracleAAEBridgeConfig, session: URLSession = .shared) {
        self.config = config
        self.session = session

        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        self.encoder = encoder

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        self.decoder = decoder
    }

    public func plan(
        goalID: String,
        objective: String,
        repoPath: String? = nil,
        stateSummary: String = "",
        constraints: [String: String] = [:],
        maxCandidates: Int? = nil
    ) async throws -> OracleAAEPlanResponse {
        guard config.enabled else {
            throw OracleAAEBridgeError.disabled
        }

        let requestBody = OracleAAEPlanRequest(
            goalID: goalID,
            objective: objective,
            repoPath: repoPath,
            stateSummary: stateSummary,
            constraints: constraints,
            maxCandidates: maxCandidates ?? config.defaultMaxCandidates
        )

        var request = URLRequest(url: config.planURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = config.timeoutSeconds
        request.httpBody = try encoder.encode(requestBody)

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw OracleAAEBridgeError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "unknown error"
            throw OracleAAEBridgeError.httpFailure(statusCode: httpResponse.statusCode, body: message)
        }

        return try decoder.decode(OracleAAEPlanResponse.self, from: data)
    }

    /// Send experiment result back to AAE for scoring and ranking updates
    public func sendExperimentResult(_ outcome: ExperimentOutcome) async throws -> ExperimentResultResponse {
        guard config.enabled else {
            throw OracleAAEBridgeError.disabled
        }

        var request = URLRequest(url: config.resultURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = config.timeoutSeconds
        request.httpBody = try encoder.encode(outcome)

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw OracleAAEBridgeError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "unknown error"
            throw OracleAAEBridgeError.httpFailure(statusCode: httpResponse.statusCode, body: message)
        }

        return try decoder.decode(ExperimentResultResponse.self, from: data)
    }
}

public enum OracleAAEBridgeError: Error, Sendable {
    case disabled
    case invalidResponse
    case httpFailure(statusCode: Int, body: String)
}
