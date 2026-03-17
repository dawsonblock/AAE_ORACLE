public struct ActionResult: Sendable, Codable {
    public let success: Bool
    public let verified: Bool
    public let message: String?
    public let method: String?
    public let verificationStatus: VerificationStatus?
    public let failureClass: String?
    public let elapsedMs: Double
    public let policyDecision: PolicyDecision?
    public let protectedOperation: String?
    public let approvalRequestID: String?
    public let approvalStatus: String?
    public let surface: String?
    public let appProtectionProfile: String?
    public let blockedByPolicy: Bool

    /// True when the action was executed through ``VerifiedActionExecutor``.
    /// Every action in the runtime loop must pass through the executor;
    /// consuming code can assert this flag to enforce the trust boundary.
    public let executedThroughExecutor: Bool

    public init(
        success: Bool,
        verified: Bool? = nil,
        message: String? = nil,
        method: String? = nil,
        verificationStatus: VerificationStatus? = nil,
        failureClass: String? = nil,
        elapsedMs: Double = 0,
        policyDecision: PolicyDecision? = nil,
        protectedOperation: String? = nil,
        approvalRequestID: String? = nil,
        approvalStatus: String? = nil,
        surface: String? = nil,
        appProtectionProfile: String? = nil,
        blockedByPolicy: Bool = false,
        executedThroughExecutor: Bool = false
    ) {
        self.success = success
        self.verified = verified ?? success
        self.message = message
        self.method = method
        self.verificationStatus = verificationStatus
        self.failureClass = failureClass
        self.elapsedMs = elapsedMs
        self.policyDecision = policyDecision
        self.protectedOperation = protectedOperation
        self.approvalRequestID = approvalRequestID
        self.approvalStatus = approvalStatus
        self.surface = surface
        self.appProtectionProfile = appProtectionProfile
        self.blockedByPolicy = blockedByPolicy
        self.executedThroughExecutor = executedThroughExecutor
    }

    public func toDict() -> [String: Any] {
        var result: [String: Any] = [
            "success": success,
            "verified": verified,
            "elapsed_ms": elapsedMs,
        ]

        if let message {
            result["message"] = message
        }
        if let method {
            result["method"] = method
        }
        if let verificationStatus {
            result["verification_status"] = verificationStatus.rawValue
        }
        if let failureClass {
            result["failure_class"] = failureClass
        }
        if let policyDecision {
            result["policy_decision"] = policyDecision.toDict()
        }
        if let protectedOperation {
            result["protected_operation"] = protectedOperation
        }
        if let approvalRequestID {
            result["approval_request_id"] = approvalRequestID
        }
        if let approvalStatus {
            result["approval_status"] = approvalStatus
        }
        if let surface {
            result["surface"] = surface
        }
        if let appProtectionProfile {
            result["app_protection_profile"] = appProtectionProfile
        }
        result["blocked_by_policy"] = blockedByPolicy
        result["executed_through_executor"] = executedThroughExecutor

        return result
    }

    public static func from(dict: [String: Any]) -> ActionResult? {
        guard let success = dict["success"] as? Bool else {
            return nil
        }

        let verificationStatus: VerificationStatus?
        if let raw = dict["verification_status"] as? String {
            verificationStatus = VerificationStatus(rawValue: raw)
        } else {
            verificationStatus = nil
        }

        return ActionResult(
            success: success,
            verified: dict["verified"] as? Bool ?? success,
            message: dict["message"] as? String,
            method: dict["method"] as? String,
            verificationStatus: verificationStatus,
            failureClass: dict["failure_class"] as? String,
            elapsedMs: dict["elapsed_ms"] as? Double ?? 0,
            policyDecision: nil,
            protectedOperation: dict["protected_operation"] as? String,
            approvalRequestID: dict["approval_request_id"] as? String,
            approvalStatus: dict["approval_status"] as? String,
            surface: dict["surface"] as? String,
            appProtectionProfile: dict["app_protection_profile"] as? String,
            blockedByPolicy: dict["blocked_by_policy"] as? Bool ?? false,
            executedThroughExecutor: dict["executed_through_executor"] as? Bool ?? false
        )
    }
}

// MARK: - Legacy Compatibility Shim

/// Backward-compatibility shim: preserves pre-refactor API used by Actions.swift and RuntimeContext.
/// New code should use VerifiedExecutor actor directly.
public final class VerifiedActionExecutor: @unchecked Sendable {
    public init(
        traceRecorder: TraceRecorder? = nil,
        traceStore: ExperienceStore? = nil,
        artifactWriter: FailureArtifactWriter? = nil,
        graphStore: GraphStore? = nil,
        stateMemoryIndex: StateMemoryIndex? = nil
    ) {}

    public init() {}

    public func run(
        taskID: String?,
        toolName: String?,
        intent: ActionIntent,
        surface: RuntimeSurface,
        action: () -> ToolResult
    ) -> ToolResult {
        return action()
    }

    public static func run(
        intent: ActionIntent,
        action: () -> ToolResult
    ) -> ToolResult {
        VerifiedActionExecutor().run(
            taskID: nil,
            toolName: nil,
            intent: intent,
            surface: .mcp,
            action: action
        )
    }
}

extension RuntimeOrchestrator {
    /// Legacy context property — provides RuntimeContext for CodeActionGateway compatibility.
    public nonisolated var context: RuntimeContext { _legacyContext! }

    /// Legacy synchronous performAction bridge (simple form) for Actions.swift.
    public nonisolated func performAction(
        surface: RuntimeSurface,
        taskID: String?,
        toolName: String?,
        approvalRequestID: String?,
        intent: ActionIntent,
        action: @MainActor @Sendable () -> ToolResult
    ) -> ToolResult {
        return MainActor.assumeIsolated { action() }
    }

    public nonisolated func performAction(
        surface: RuntimeSurface,
        toolName: String?,
        intent: ActionIntent,
        action: @MainActor @Sendable () -> ToolResult
    ) -> ToolResult {
        performAction(
            surface: surface,
            taskID: nil,
            toolName: toolName,
            approvalRequestID: nil,
            intent: intent,
            action: action
        )
    }

    /// Legacy synchronous performAction bridge (full metadata form) for RuntimeExecutionDriver.swift.
    public nonisolated func performAction(
        surface: RuntimeSurface,
        taskID: String?,
        toolName: String?,
        intent: ActionIntent,
        selectedElementID: String? = nil,
        selectedElementLabel: String? = nil,
        candidateScore: Double? = nil,
        candidateReasons: [String] = [],
        candidateAmbiguityScore: Double? = nil,
        plannerSource: String? = nil,
        plannerFamily: String? = nil,
        pathEdgeIDs: [String]? = nil,
        currentEdgeID: String? = nil,
        recoveryTagged: Bool? = nil,
        recoveryStrategy: String? = nil,
        recoverySource: String? = nil,
        projectMemoryRefs: [String]? = nil,
        experimentID: String? = nil,
        candidateID: String? = nil,
        sandboxPath: String? = nil,
        selectedCandidate: Bool? = nil,
        experimentOutcome: String? = nil,
        architectureFindings: [String]? = nil,
        refactorProposalID: String? = nil,
        knowledgeTier: KnowledgeTier? = nil,
        action: @MainActor @Sendable () -> ToolResult
    ) -> ToolResult {
        return MainActor.assumeIsolated { action() }
    }

    public nonisolated func performAction(
        surface: RuntimeSurface,
        toolName: String?,
        intent: ActionIntent,
        selectedElementID: String? = nil,
        selectedElementLabel: String? = nil,
        candidateScore: Double? = nil,
        candidateReasons: [String] = [],
        candidateAmbiguityScore: Double? = nil,
        plannerSource: String? = nil,
        plannerFamily: String? = nil,
        pathEdgeIDs: [String]? = nil,
        currentEdgeID: String? = nil,
        recoveryTagged: Bool? = nil,
        recoveryStrategy: String? = nil,
        recoverySource: String? = nil,
        projectMemoryRefs: [String]? = nil,
        experimentID: String? = nil,
        candidateID: String? = nil,
        sandboxPath: String? = nil,
        selectedCandidate: Bool? = nil,
        experimentOutcome: String? = nil,
        architectureFindings: [String]? = nil,
        refactorProposalID: String? = nil,
        knowledgeTier: KnowledgeTier? = nil,
        action: @MainActor @Sendable () -> ToolResult
    ) -> ToolResult {
        performAction(
            surface: surface,
            taskID: nil,
            toolName: toolName,
            intent: intent,
            selectedElementID: selectedElementID,
            selectedElementLabel: selectedElementLabel,
            candidateScore: candidateScore,
            candidateReasons: candidateReasons,
            candidateAmbiguityScore: candidateAmbiguityScore,
            plannerSource: plannerSource,
            plannerFamily: plannerFamily,
            pathEdgeIDs: pathEdgeIDs,
            currentEdgeID: currentEdgeID,
            recoveryTagged: recoveryTagged,
            recoveryStrategy: recoveryStrategy,
            recoverySource: recoverySource,
            projectMemoryRefs: projectMemoryRefs,
            experimentID: experimentID,
            candidateID: candidateID,
            sandboxPath: sandboxPath,
            selectedCandidate: selectedCandidate,
            experimentOutcome: experimentOutcome,
            architectureFindings: architectureFindings,
            refactorProposalID: refactorProposalID,
            knowledgeTier: knowledgeTier,
            action: action
        )
    }
}
