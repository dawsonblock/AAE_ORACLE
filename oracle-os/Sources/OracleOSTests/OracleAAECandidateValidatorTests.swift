import Foundation
import XCTest

// Import the modules under test
// Note: In a real project, these would be imported from the module
// For now, we define test helpers that mirror the validator logic

// ============================================================================
// MARK: - Test Helpers (Mirrors OracleAAECandidateValidator)
// ============================================================================

/// Test candidate structure matching OracleAAECandidate
struct TestCandidate {
    let candidateID: String
    let kind: String
    let tool: String
    let payload: [String: Any]
    let rationale: String
    let confidence: Double
    let predictedScore: Double
    let safetyClass: String
    
    // Phase 3 fields
    let targetFile: String?
    let rankedFallbackPaths: [String]?
    let recommendedTestCommand: String?
    let dominantLanguage: String?
    let patchFileCountLimit: Int?
}

/// Validation result structure
struct TestValidationResult {
    let isValid: Bool
    let rejectionReasons: [String]
    let requiresApprovalCandidates: [String]
    let mappedSkillName: String?
    let mappedCommandCategory: String?
}

/// Validation report structure
struct TestValidationReport {
    let totalCandidates: Int
    let validCandidates: Int
    let rejectedCandidates: Int
    let requiresApprovalCount: Int
    let validationResults: [String: TestValidationResult]
    let allRejectionReasons: [String]
    let schemaVersion: String
}

// Allowed enum values (from OracleAAECandidateValidator)
let validKinds: Set<String> = [
    "aae.inspect_repository",
    "aae.analyze_objective",
    "aae.run_targeted_tests",
    "aae.localize_failure",
    "aae.generate_patch",
    "aae.validate_candidate",
    "aae.estimate_change_impact"
]

let validTools: Set<String> = [
    "repository_analyzer",
    "planner_service",
    "sandbox",
    "localization_service",
    "patch_engine",
    "verifier",
    "graph_service"
]

let validSafetyClasses: Set<String> = [
    "read_only",
    "bounded_mutation",
    "requires_approval",
    "sandboxed_write"
]

/// Test validator function (mirrors OracleAAECandidateValidator)
func validateCandidate(_ candidate: TestCandidate) -> TestValidationResult {
    var rejectionReasons: [String] = []
    
    // 1. Validate kind
    if !validKinds.contains(candidate.kind) {
        rejectionReasons.append("Unknown candidate_kind: \"\(candidate.kind)\"")
    }
    
    // 2. Validate tool_name
    if !validTools.contains(candidate.tool) {
        rejectionReasons.append("Unknown tool_name: \"\(candidate.tool)\"")
    }
    
    // 3. Validate required fields
    if candidate.rationale.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
        rejectionReasons.append("Missing required field: rationale (empty or whitespace)")
    }
    
    // 4. Validate confidence bounds
    if candidate.confidence.isNaN || candidate.confidence.isInfinite {
        rejectionReasons.append("Invalid confidence: not a finite number")
    } else if candidate.confidence < 0.0 || candidate.confidence > 1.0 {
        rejectionReasons.append("confidence out of bounds: \(candidate.confidence) (must be 0.0-1.0)")
    }
    
    // 5. Validate safety_class
    if !validSafetyClasses.contains(candidate.safetyClass) {
        rejectionReasons.append("Invalid safety_class: \"\(candidate.safetyClass)\"")
    }
    
    // Check for requires_approval
    var requiresApprovalCandidates: [String] = []
    if candidate.safetyClass == "requires_approval" {
        requiresApprovalCandidates.append(candidate.candidateID)
    }
    
    if rejectionReasons.isEmpty {
        // Map to Oracle command types
        let skillName = mappedSkillName(for: candidate.kind)
        let commandCategory = mappedCommandCategory(for: skillName)
        return TestValidationResult(
            isValid: true,
            rejectionReasons: [],
            requiresApprovalCandidates: requiresApprovalCandidates,
            mappedSkillName: skillName,
            mappedCommandCategory: commandCategory
        )
    } else {
        return TestValidationResult(
            isValid: false,
            rejectionReasons: rejectionReasons,
            requiresApprovalCandidates: [],
            mappedSkillName: nil,
            mappedCommandCategory: nil
        )
    }
}

func mappedSkillName(for kind: String) -> String? {
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

func mappedCommandCategory(for skillName: String?) -> String? {
    guard let skillName else { return nil }
    switch skillName {
    case "read_repository":
        return "indexRepository"
    case "search_code":
        return "searchCode"
    case "generate_patch":
        return "generatePatch"
    case "run_tests":
        return "test"
    default:
        return nil
    }
}

func validateCandidates(_ candidates: [TestCandidate]) -> TestValidationReport {
    var validationResults: [String: TestValidationResult] = [:]
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
        
        requiresApprovalCount += result.requiresApprovalCandidates.count
    }
    
    return TestValidationReport(
        totalCandidates: candidates.count,
        validCandidates: validCount,
        rejectedCandidates: candidates.count - validCount,
        requiresApprovalCount: requiresApprovalCount,
        validationResults: validationResults,
        allRejectionReasons: allRejectionReasons
    )
}

// ============================================================================
// MARK: - XCTest Case
// ============================================================================

final class OracleAAECandidateValidatorTests: XCTestCase {
    
    // MARK: - Test: Decode Failures
    
    func testMalformedJSONDecodeFailure() throws {
        // Test that malformed JSON is properly rejected
        let malformedJSON = """
        {"goal_id": "test", "objective": }
        """
        
        let data = malformedJSON.data(using: .utf8)!
        
        // Attempting to decode should fail
        XCTAssertThrowsError(try JSONDecoder().decode(TestCandidate.self, from: data)) { error in
            // Expected: JSON decoding error
            XCTAssertTrue(error.localizedDescription.contains("Unable to parse"))
        }
    }
    
    func testMissingRequiredFieldsDecodeFailure() throws {
        // Test that missing required fields cause decode failures
        let incompleteJSON = """
        {"candidate_id": "test-001"}
        """
        
        let data = incompleteJSON.data(using: .utf8)!
        
        // Should fail because required fields are missing
        XCTAssertThrowsError(try JSONDecoder().decode(TestCandidate.self, from: data))
    }
    
    func testInvalidFieldTypesDecodeFailure() throws {
        // Test that wrong field types cause decode failures
        let invalidTypeJSON = """
        {
            "candidate_id": "test-001",
            "kind": "aae.inspect_repository",
            "tool": "repository_analyzer",
            "payload": {},
            "rationale": "Test candidate",
            "confidence": "not-a-number",
            "predicted_score": 0.5,
            "safety_class": "read_only"
        }
        """
        
        let data = invalidTypeJSON.data(using: .utf8)!
        
        // Should fail because confidence should be a number
        XCTAssertThrowsError(try JSONDecoder().decode(TestCandidate.self, from: data))
    }
    
    // MARK: - Test: Unsupported Tool Mapping
    
    func testUnknownToolMapping() {
        // Test that unknown tools are rejected
        let candidate = TestCandidate(
            candidateID: "test-tool-001",
            kind: "aae.inspect_repository",
            tool: "unknown_tool_executor",
            payload: [:],
            rationale: "This tool should be rejected",
            confidence: 0.8,
            predictedScore: 0.7,
            safetyClass: "read_only",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertFalse(result.isValid, "Unknown tool should be rejected")
        XCTAssertTrue(result.rejectionReasons.contains { $0.contains("Unknown tool_name") })
    }
    
    func testUnknownKindMapping() {
        // Test that unknown kinds are rejected
        let candidate = TestCandidate(
            candidateID: "test-kind-001",
            kind: "aae.execute_arbitrary_command",
            tool: "sandbox",
            payload: [:],
            rationale: "Unknown kind should be rejected",
            confidence: 0.8,
            predictedScore: 0.7,
            safetyClass: "read_only",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertFalse(result.isValid, "Unknown kind should be rejected")
        XCTAssertTrue(result.rejectionReasons.contains { $0.contains("Unknown candidate_kind") })
    }
    
    // MARK: - Test: Confidence Edge Cases
    
    func testConfidenceMinimumBoundary() {
        // Test confidence = 0.0 (should be valid)
        let candidate = TestCandidate(
            candidateID: "test-conf-001",
            kind: "aae.inspect_repository",
            tool: "repository_analyzer",
            payload: [:],
            rationale: "Valid with minimum confidence",
            confidence: 0.0,
            predictedScore: 0.1,
            safetyClass: "read_only",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertTrue(result.isValid, "Confidence of 0.0 should be valid")
        XCTAssertEqual(result.mappedSkillName, "read_repository")
    }
    
    func testConfidenceMaximumBoundary() {
        // Test confidence = 1.0 (should be valid)
        let candidate = TestCandidate(
            candidateID: "test-conf-002",
            kind: "aae.generate_patch",
            tool: "patch_engine",
            payload: [:],
            rationale: "Valid with maximum confidence",
            confidence: 1.0,
            predictedScore: 0.95,
            safetyClass: "bounded_mutation",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertTrue(result.isValid, "Confidence of 1.0 should be valid")
    }
    
    func testConfidenceNegativeRejected() {
        // Test negative confidence (should be invalid)
        let candidate = TestCandidate(
            candidateID: "test-conf-003",
            kind: "aae.inspect_repository",
            tool: "repository_analyzer",
            payload: [:],
            rationale: "Negative confidence should be rejected",
            confidence: -0.1,
            predictedScore: 0.5,
            safetyClass: "read_only",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertFalse(result.isValid, "Negative confidence should be rejected")
        XCTAssertTrue(result.rejectionReasons.contains { $0.contains("out of bounds") })
    }
    
    func testConfidenceGreaterThanOneRejected() {
        // Test confidence > 1.0 (should be invalid)
        let candidate = TestCandidate(
            candidateID: "test-conf-004",
            kind: "aae.inspect_repository",
            tool: "repository_analyzer",
            payload: [:],
            rationale: "Confidence > 1.0 should be rejected",
            confidence: 1.5,
            predictedScore: 0.9,
            safetyClass: "read_only",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertFalse(result.isValid, "Confidence > 1.0 should be rejected")
        XCTAssertTrue(result.rejectionReasons.contains { $0.contains("out of bounds") })
    }
    
    func testConfidenceNaNRejected() {
        // Test NaN confidence (should be invalid)
        let candidate = TestCandidate(
            candidateID: "test-conf-005",
            kind: "aae.inspect_repository",
            tool: "repository_analyzer",
            payload: [:],
            rationale: "NaN confidence should be rejected",
            confidence: Double.nan,
            predictedScore: 0.5,
            safetyClass: "read_only",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertFalse(result.isValid, "NaN confidence should be rejected")
    }
    
    func testConfidenceInfinityRejected() {
        // Test Infinity confidence (should be invalid)
        let candidate = TestCandidate(
            candidateID: "test-conf-006",
            kind: "aae.inspect_repository",
            tool: "repository_analyzer",
            payload: [:],
            rationale: "Infinity confidence should be rejected",
            confidence: Double.infinity,
            predictedScore: 0.5,
            safetyClass: "read_only",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertFalse(result.isValid, "Infinity confidence should be rejected")
    }
    
    // MARK: - Test: Rationale Validation
    
    func testEmptyRationaleRejected() {
        // Test empty rationale (should be invalid)
        let candidate = TestCandidate(
            candidateID: "test-ratio-001",
            kind: "aae.inspect_repository",
            tool: "repository_analyzer",
            payload: [:],
            rationale: "",
            confidence: 0.8,
            predictedScore: 0.7,
            safetyClass: "read_only",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertFalse(result.isValid, "Empty rationale should be rejected")
        XCTAssertTrue(result.rejectionReasons.contains { $0.contains("rationale") })
    }
    
    func testWhitespaceRationaleRejected() {
        // Test whitespace-only rationale (should be invalid)
        let candidate = TestCandidate(
            candidateID: "test-ratio-002",
            kind: "aae.inspect_repository",
            tool: "repository_analyzer",
            payload: [:],
            rationale: "   ",
            confidence: 0.8,
            predictedScore: 0.7,
            safetyClass: "read_only",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertFalse(result.isValid, "Whitespace rationale should be rejected")
    }
    
    // MARK: - Test: Safety Class Validation
    
    func testInvalidSafetyClassRejected() {
        // Test invalid safety class (should be rejected)
        let candidate = TestCandidate(
            candidateID: "test-safety-001",
            kind: "aae.generate_patch",
            tool: "patch_engine",
            payload: [:],
            rationale: "Invalid safety class should be rejected",
            confidence: 0.8,
            predictedScore: 0.7,
            safetyClass: "dangerous_operation",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertFalse(result.isValid, "Invalid safety class should be rejected")
        XCTAssertTrue(result.rejectionReasons.contains { $0.contains("safety_class") })
    }
    
    func testRequiresApprovalFlagged() {
        // Test that requires_approval is properly flagged
        let candidate = TestCandidate(
            candidateID: "test-approval-001",
            kind: "aae.generate_patch",
            tool: "patch_engine",
            payload: [:],
            rationale: "This should require approval",
            confidence: 0.9,
            predictedScore: 0.8,
            safetyClass: "requires_approval",
            targetFile: nil,
            rankedFallbackPaths: nil,
            recommendedTestCommand: nil,
            dominantLanguage: nil,
            patchFileCountLimit: nil
        )
        
        let result = validateCandidate(candidate)
        
        XCTAssertTrue(result.isValid, "Valid candidate with requires_approval")
        XCTAssertTrue(result.requiresApprovalCandidates.contains("test-approval-001"))
    }
    
    // MARK: - Test: Skill Mapping
    
    func testValidKindMapping() {
        // Test that valid kinds are mapped to correct skills
        let testCases: [(kind: String, expectedSkill: String)] = [
            ("aae.inspect_repository", "read_repository"),
            ("aae.analyze_objective", "read_repository"),
            ("aae.run_targeted_tests", "run_tests"),
            ("aae.validate_candidate", "run_tests"),
            ("aae.localize_failure", "search_code"),
            ("aae.estimate_change_impact", "search_code"),
            ("aae.generate_patch", "generate_patch")
        ]
        
        for testCase in testCases {
            let candidate = TestCandidate(
                candidateID: "map-\(testCase.kind)",
                kind: testCase.kind,
                tool: "sandbox",
                payload: [:],
                rationale: "Testing skill mapping",
                confidence: 0.8,
                predictedScore: 0.7,
                safetyClass: "read_only",
                targetFile: nil,
                rankedFallbackPaths: nil,
                recommendedTestCommand: nil,
                dominantLanguage: nil,
                patchFileCountLimit: nil
            )
            
            let result = validateCandidate(candidate)
            
            XCTAssertEqual(
                result.mappedSkillName,
                testCase.expectedSkill,
                "Kind \(testCase.kind) should map to \(testCase.expectedSkill)"
            )
        }
    }
    
    // MARK: - Test: Validation Report
    
    func testValidationReportMultipleCandidates() {
        // Test validation report with multiple candidates
        let candidates = [
            TestCandidate(
                candidateID: "valid-001",
                kind: "aae.inspect_repository",
                tool: "repository_analyzer",
                payload: [:],
                rationale: "Valid candidate",
                confidence: 0.8,
                predictedScore: 0.7,
                safetyClass: "read_only",
                targetFile: nil,
                rankedFallbackPaths: nil,
                recommendedTestCommand: nil,
                dominantLanguage: nil,
                patchFileCountLimit: nil
            ),
            TestCandidate(
                candidateID: "invalid-001",
                kind: "aae.unknown_kind",
                tool: "repository_analyzer",
                payload: [:],
                rationale: "Invalid kind",
                confidence: 0.8,
                predictedScore: 0.7,
                safetyClass: "read_only",
                targetFile: nil,
                rankedFallbackPaths: nil,
                recommendedTestCommand: nil,
                dominantLanguage: nil,
                patchFileCountLimit: nil
            ),
            TestCandidate(
                candidateID: "valid-002",
                kind: "aae.run_targeted_tests",
                tool: "sandbox",
                payload: [:],
                rationale: "Valid candidate requiring approval",
                confidence: 0.9,
                predictedScore: 0.8,
                safetyClass: "requires_approval",
                targetFile: nil,
                rankedFallbackPaths: nil,
                recommendedTestCommand: nil,
                dominantLanguage: nil,
                patchFileCountLimit: nil
            )
        ]
        
        let report = validateCandidates(candidates)
        
        XCTAssertEqual(report.totalCandidates, 3)
        XCTAssertEqual(report.validCandidates, 2)
        XCTAssertEqual(report.rejectedCandidates, 1)
        XCTAssertEqual(report.requiresApprovalCount, 1)
    }
    
    // MARK: - Test: Fallback When Bridge Unavailable
    
    func testFallbackBehaviorForInvalidCandidates() {
        // Test that invalid candidates are handled gracefully (fallback behavior)
        let candidates = [
            TestCandidate(
                candidateID: "bridge-fail-001",
                kind: "aae.unknown_bridge_tool",
                tool: "unknown_tool",
                payload: [:],
                rationale: "Completely invalid candidate",
                confidence: -1.0,  // Invalid
                predictedScore: 0.5,
                safetyClass: "invalid_safety",
                targetFile: nil,
                rankedFallbackPaths: nil,
                recommendedTestCommand: nil,
                dominantLanguage: nil,
                patchFileCountLimit: nil
            )
        ]
        
        let report = validateCandidates(candidates)
        
        // All invalid candidates should be rejected
        XCTAssertEqual(report.rejectedCandidates, 1)
        XCTAssertEqual(report.validCandidates, 0)
        
        // The rejection reasons should be informative
        XCTAssertFalse(report.allRejectionReasons.isEmpty)
    }
    
    // MARK: - Test: Round-Trip Validation
    
    func testRoundTripValidation() {
        // Test complete round-trip: create candidate -> validate -> check result
        let originalCandidate = TestCandidate(
            candidateID: "roundtrip-001",
            kind: "aae.generate_patch",
            tool: "patch_engine",
            payload: ["target_file": "src/main.swift"],
            rationale: "Generate patch for main.swift",
            confidence: 0.85,
            predictedScore: 0.75,
            safetyClass: "bounded_mutation",
            targetFile: "src/main.swift",
            rankedFallbackPaths: ["lib/main.swift", "app/main.swift"],
            recommendedTestCommand: "pytest tests/",
            dominantLanguage: "python",
            patchFileCountLimit: 3
        )
        
        let result = validateCandidate(originalCandidate)
        
        // Should be valid with correct mappings
        XCTAssertTrue(result.isValid)
        XCTAssertEqual(result.mappedSkillName, "generate_patch")
        XCTAssertEqual(result.mappedCommandCategory, "generatePatch")
        XCTAssertEqual(result.requiresApprovalCandidates.count, 0)
    }
    
    // MARK: - Test: All Valid Kinds
    
    func testAllValidKinds() {
        // Test that all valid kinds pass kind validation
        let validKindsList = [
            "aae.inspect_repository",
            "aae.analyze_objective",
            "aae.run_targeted_tests",
            "aae.localize_failure",
            "aae.generate_patch",
            "aae.validate_candidate",
            "aae.estimate_change_impact"
        ]
        
        for kind in validKindsList {
            let candidate = TestCandidate(
                candidateID: "valid-kind-\(kind)",
                kind: kind,
                tool: "repository_analyzer",
                payload: [:],
                rationale: "Valid kind test",
                confidence: 0.8,
                predictedScore: 0.7,
                safetyClass: "read_only",
                targetFile: nil,
                rankedFallbackPaths: nil,
                recommendedTestCommand: nil,
                dominantLanguage: nil,
                patchFileCountLimit: nil
            )
            
            let result = validateCandidate(candidate)
            
            XCTAssertTrue(
                result.isValid,
                "Kind '\(kind)' should be valid but got errors: \(result.rejectionReasons)"
            )
        }
    }
    
    // MARK: - Test: All Valid Tools
    
    func testAllValidTools() {
        // Test that all valid tools pass tool validation
        let validToolsList = [
            "repository_analyzer",
            "planner_service",
            "sandbox",
            "localization_service",
            "patch_engine",
            "verifier",
            "graph_service"
        ]
        
        for tool in validToolsList {
            let candidate = TestCandidate(
                candidateID: "valid-tool-\(tool)",
                kind: "aae.inspect_repository",
                tool: tool,
                payload: [:],
                rationale: "Valid tool test",
                confidence: 0.8,
                predictedScore: 0.7,
                safetyClass: "read_only",
                targetFile: nil,
                rankedFallbackPaths: nil,
                recommendedTestCommand: nil,
                dominantLanguage: nil,
                patchFileCountLimit: nil
            )
            
            let result = validateCandidate(candidate)
            
            XCTAssertTrue(
                result.isValid,
                "Tool '\(tool)' should be valid but got errors: \(result.rejectionReasons)"
            )
        }
    }
}