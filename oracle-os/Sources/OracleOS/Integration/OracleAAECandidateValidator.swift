import Foundation

// MARK: - Allowed Enums

public enum OracleAAECandidateKind: String, CaseIterable, Sendable {
    case inspectRepository = "aae.inspect_repository"
    case analyzeObjective = "aae.analyze_objective"
    case runTargetedTests = "aae.run_targeted_tests"
    case localizeFailure = "aae.localize_failure"
    case generatePatch = "aae.generate_patch"
    case validateCandidate = "aae.validate_candidate"
    case estimateChangeImpact = "aae.estimate_change_impact"

    public var isValid: Bool { true }
}

public enum OracleAAEToolName: String, CaseIterable, Sendable {
    case repositoryAnalyzer = "repository_analyzer"
    case plannerService = "planner_service"
    case sandbox = "sandbox"
    case localizationService = "localization_service"
    case patchEngine = "patch_engine"
    case verifier = "verifier"
    case graphService = "graph_service"

    public var isValid: Bool { true }
}

public enum OracleAAESafetyClass: String, CaseIterable, Sendable {
    case readOnly = "read_only"
    case boundedMutation = "bounded_mutation"
    case requiresApproval = "requires_approval"
    case sandboxedWrite = "sandboxed_write"

    public var requiresApproval: Bool {
        self == .requiresApproval
    }
}

/// Strict candidate type for fail-fast decoding.
/// Matches Literal["patch", "refactor", "config"] on the Python side.
public enum CandidateType: String, Codable, Sendable {
    case patch
    case refactor
    case config
}

/// Risk level for capability gating.
public enum CandidateRisk: String, Codable, Sendable {
    case low
    case medium
    case high
}

// MARK: - Confidence Gating

public enum CapabilityGatingError: Error, Sendable {
    case lowConfidence(Double)
    case highRisk(String)
}

// MARK: - Validation Result

public struct OracleAAECandidateValidationResult: Sendable {
    public let isValid: Bool
    public let rejectionReasons: [String]
    public let requiresApprovalCandidates: [String]
    public let mappedSkillName: String?
    public let mappedCommandCategory: String?

    public init(
        isValid: Bool,
        rejectionReasons: [String] = [],
        requiresApprovalCandidates: [String] = [],
        mappedSkillName: String? = nil,
        mappedCommandCategory: String? = nil
    ) {
        self.isValid = isValid
        self.rejectionReasons = rejectionReasons
        self.requiresApprovalCandidates = requiresApprovalCandidates
        self.mappedSkillName = mappedSkillName
        self.mappedCommandCategory = mappedCommandCategory
    }

    public static func valid(skillName: String, commandCategory: String) -> OracleAAECandidateValidationResult {
        OracleAAECandidateValidationResult(
            isValid: true,
            mappedSkillName: skillName,
            mappedCommandCategory: commandCategory
        )
    }

    public static func invalid(reasons: [String]) -> OracleAAECandidateValidationResult {
        OracleAAECandidateValidationResult(
            isValid: false,
            rejectionReasons: reasons
        )
    }
}

public struct OracleAAEValidationReport: Sendable {
    public let totalCandidates: Int
    public let validCandidates: Int
    public let rejectedCandidates: Int
    public let requiresApprovalCount: Int
    public let validationResults: [String: OracleAAECandidateValidationResult]
    public let allRejectionReasons: [String]
    public let schemaVersion: String

    public init(
        totalCandidates: Int,
        validCandidates: Int,
        rejectedCandidates: Int,
        requiresApprovalCount: Int,
        validationResults: [String: OracleAAECandidateValidationResult],
        allRejectionReasons: [String],
        schemaVersion: String = "aae.candidate.v1"
    ) {
        self.totalCandidates = totalCandidates
        self.validCandidates = validCandidates
        self.rejectedCandidates = rejectedCandidates
        self.requiresApprovalCount = requiresApprovalCount
        self.validationResults = validationResults
        self.allRejectionReasons = allRejectionReasons
        self.schemaVersion = schemaVersion
    }
}

// MARK: - Validator

public actor OracleAAECandidateValidator {
    private let validKinds: Set<String>
    private let validTools: Set<String>
    private let validSafetyClasses: Set<String>
    private var validationMetrics: ValidationMetrics

    private struct ValidationMetrics: Sendable {
        var totalValidated: Int = 0
        var totalRejected: Int = 0
        var totalRequiresApproval: Int = 0
        var rejectionReasons: [String: Int] = [:]

        mutating func recordValidation(_ result: OracleAAECandidateValidationResult) {
            totalValidated += 1
            if !result.isValid {
                totalRejected += 1
                for reason in result.rejectionReasons {
                    rejectionReasons[reason, default: 0] += 1
                }
            }
            if !result.requiresApprovalCandidates.isEmpty {
                totalRequiresApproval += result.requiresApprovalCandidates.count
            }
        }
    }

    public init() {
        self.validKinds = Set(OracleAAECandidateKind.allCases.map(\.rawValue))
        self.validTools = Set(OracleAAEToolName.allCases.map(\.rawValue))
        self.validSafetyClasses = Set(OracleAAESafetyClass.allCases.map(\.rawValue))
        self.validationMetrics = ValidationMetrics()
    }

    // MARK: - Public API

    public func validateCandidates(_ candidates: [OracleAAECandidate]) -> OracleAAEValidationReport {
        var validationResults: [String: OracleAAECandidateValidationResult] = [:]
        var allRejectionReasons: [String] = []
        var validCount = 0
        var requiresApprovalCount = 0

        for candidate in candidates {
            let result = validateCandidate(candidate)
            validationResults[candidate.candidateID] = result

            if result.isValid {
                validCount += 1
            } else {
                allRejectionReasons.append(contentsOf: result.rejectionReasons.map { "[\(candidate.candidateID)] \($0)" })
            }

            if !result.requiresApprovalCandidates.isEmpty {
                requiresApprovalCount += result.requiresApprovalCandidates.count
            }

            validationMetrics.recordValidation(result)
        }

        return OracleAAEValidationReport(
            totalCandidates: candidates.count,
            validCandidates: validCount,
            rejectedCandidates: candidates.count - validCount,
            requiresApprovalCount: requiresApprovalCount,
            validationResults: validationResults,
            allRejectionReasons: allRejectionReasons
        )
    }

    public func validateCandidate(_ candidate: OracleAAECandidate) -> OracleAAECandidateValidationResult {
        var rejectionReasons: [String] = []

        // 1. Validate kind
        let kindValidation = validateKind(candidate.kind)
        if !kindValidation.isValid {
            rejectionReasons.append(kindValidation.error ?? "unknown error")
        }

        // 2. Validate tool_name
        let toolValidation = validateToolName(candidate.tool)
        if !toolValidation.isValid {
            rejectionReasons.append(toolValidation.error ?? "unknown error")
        }

        // 3. Validate required fields
        let requiredValidation = validateRequiredFields(candidate)
        rejectionReasons.append(contentsOf: requiredValidation.errors)

        // 4. Validate confidence bounds
        let confidenceValidation = validateConfidence(candidate.confidence)
        if !confidenceValidation.isValid {
            rejectionReasons.append(confidenceValidation.error ?? "unknown error")
        }

        // 5. Check for requires_approval
        var requiresApprovalCandidates: [String] = []
        if candidate.safetyClass == OracleAAESafetyClass.requiresApproval.rawValue {
            requiresApprovalCandidates.append(candidate.candidateID)
        }

        if rejectionReasons.isEmpty {
            // Map to Oracle command types
            let skillName = mappedSkillName(for: candidate.kind)
            let commandCategory = mappedCommandCategory(for: skillName)
            return OracleAAECandidateValidationResult.valid(
                skillName: skillName ?? "",
                commandCategory: commandCategory ?? ""
            )
        } else {
            return OracleAAECandidateValidationResult.invalid(reasons: rejectionReasons)
        }
    }

    // MARK: - Validation Helpers

    private func validateKind(_ kind: String) -> (isValid: Bool, error: String?) {
        if validKinds.contains(kind) {
            return (true, nil)
        }
        return (false, "Unknown candidate_kind: \"\(kind)\"")
    }

    private func validateToolName(_ toolName: String) -> (isValid: Bool, error: String?) {
        if validTools.contains(toolName) {
            return (true, nil)
        }
        return (false, "Unknown tool_name: \"\(toolName)\"")
    }

    private func validateRequiredFields(_ candidate: OracleAAECandidate) -> (isValid: Bool, errors: [String]) {
        var errors: [String] = []

        // Validate rationale
        if candidate.rationale.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            errors.append("Missing required field: rationale (empty or whitespace)")
        }

        // Validate confidence exists and is in bounds (already checked separately, but ensure non-nil)
        if candidate.confidence.isNaN || candidate.confidence.isInfinite {
            errors.append("Invalid confidence: not a finite number")
        }

        // Validate safety_class
        if !validSafetyClasses.contains(candidate.safetyClass) {
            errors.append("Invalid safety_class: \"\(candidate.safetyClass)\"")
        }

        return (errors.isEmpty, errors)
    }

    private func validateConfidence(_ confidence: Double) -> (isValid: Bool, error: String?) {
        guard confidence >= 0.0 && confidence <= 1.0 else {
            return (false, "confidence out of bounds: \(confidence) (must be 0.0-1.0)")
        }
        return (true, nil)
    }

    // MARK: - Command Mapping

    public func mappedSkillName(for kind: String) -> String? {
        switch kind {
        case OracleAAECandidateKind.inspectRepository.rawValue,
             OracleAAECandidateKind.analyzeObjective.rawValue:
            return "read_repository"
        case OracleAAECandidateKind.runTargetedTests.rawValue,
             OracleAAECandidateKind.validateCandidate.rawValue:
            return "run_tests"
        case OracleAAECandidateKind.localizeFailure.rawValue,
             OracleAAECandidateKind.estimateChangeImpact.rawValue:
            return "search_code"
        case OracleAAECandidateKind.generatePatch.rawValue:
            return "generate_patch"
        default:
            return nil
        }
    }

    public func mappedCommandCategory(for skillName: String?) -> String? {
        guard let skillName else { return nil }
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

    // MARK: - Metrics

    public func getMetrics() -> (totalValidated: Int, totalRejected: Int, totalRequiresApproval: Int, rejectionReasons: [String: Int]) {
        (
            totalValidated: validationMetrics.totalValidated,
            totalRejected: validationMetrics.totalRejected,
            totalRequiresApproval: validationMetrics.totalRequiresApproval,
            rejectionReasons: validationMetrics.rejectionReasons
        )
    }

    public func resetMetrics() {
        validationMetrics = ValidationMetrics()
    }

    // MARK: - Capability Gating (Phase 8)

    /// Reject candidates below confidence threshold.
    public func enforceConfidenceGate(_ candidate: OracleAAECandidate, threshold: Double = 0.6) throws {
        if candidate.confidence < threshold {
            throw CapabilityGatingError.lowConfidence(candidate.confidence)
        }
    }

    /// Risk-aware execution gating.
    /// - low → auto-execute
    /// - medium → simulate first (returns .medium)
    /// - high → reject
    public func assessRisk(_ candidate: OracleAAECandidate) throws -> CandidateRisk {
        // Determine risk from safety class
        let risk: CandidateRisk
        switch candidate.safetyClass {
        case OracleAAESafetyClass.readOnly.rawValue:
            risk = .low
        case OracleAAESafetyClass.sandboxedWrite.rawValue,
             OracleAAESafetyClass.boundedMutation.rawValue:
            risk = .medium
        case OracleAAESafetyClass.requiresApproval.rawValue:
            risk = .high
        default:
            risk = .high
        }

        if risk == .high {
            throw CapabilityGatingError.highRisk(candidate.safetyClass)
        }

        return risk
    }
}

// MARK: - Convenience Extension

extension OracleAAECandidateValidator {
    public func filterValidCandidates(_ candidates: [OracleAAECandidate]) -> (valid: [OracleAAECandidate], report: OracleAAEValidationReport) {
        let report = validateCandidates(candidates)
        let validCandidates = candidates.filter { candidate in
            guard let result = report.validationResults[candidate.candidateID] else {
                return false
            }
            return result.isValid
        }
        return (validCandidates, report)
    }
}
