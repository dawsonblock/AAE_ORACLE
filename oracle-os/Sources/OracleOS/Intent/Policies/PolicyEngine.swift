import Foundation

public final class PolicyEngine: @unchecked Sendable {
    public static let shared = PolicyEngine()

    public var mode: PolicyMode

    /// Cache for policy decisions to avoid repeated evaluation
    private var decisionCache: [String: CachedDecision] = [:]
    private let cacheLock = NSLock()

    /// Cache TTL in seconds (default 5 minutes)
    private let cacheTTL: TimeInterval = 300

    /// Cached decision with timestamp for TTL tracking
    private struct CachedDecision {
        let decision: PolicyDecision
        let timestamp: Date

        var isExpired: Bool {
            Date().timeIntervalSince(timestamp) > 300
        }
    }

    public init(mode: PolicyMode? = nil) {
        self.mode = mode ?? Self.defaultMode()
    }

    /// Clear the policy decision cache (call after hot-reload)
    public func clearCache() {
        cacheLock.lock()
        defer { cacheLock.unlock() }
        decisionCache.removeAll()
        Log.info("PolicyEngine: Decision cache cleared")
    }

    /// Reload policies with immediate cache invalidation
    public func reloadPolicies(mode: PolicyMode? = nil) {
        if let mode = mode {
            self.mode = mode
        }
        clearCache()
    }

    public func evaluate(intent: ActionIntent) -> PolicyDecision {
        evaluate(
            intent: intent,
            context: PolicyEvaluationContext(
                surface: .mcp,
                toolName: nil,
                appName: intent.app,
                agentKind: intent.agentKind,
                workspaceRoot: intent.workspaceRoot,
                workspaceRelativePath: intent.workspaceRelativePath,
                commandCategory: intent.commandCategory
            )
        )
    }

    public func evaluate(intent: ActionIntent, context: PolicyEvaluationContext) -> PolicyDecision {
        let appProtectionProfile = PolicyRules.appProtectionProfile(for: context.appName ?? intent.app)
        let classification = PolicyRules.classification(
            for: intent,
            context: context,
            appProtectionProfile: appProtectionProfile
        )
        let protectedOperation = classification.protectedOperation
        let riskLevel = classification.riskLevel

        let baseDecision = PolicyDecision(
            allowed: riskLevel == .low,
            riskLevel: riskLevel,
            protectedOperation: protectedOperation,
            appProtectionProfile: appProtectionProfile,
            blockedByPolicy: riskLevel == .blocked,
            surface: context.surface,
            policyMode: mode,
            requiresApproval: riskLevel == .risky,
            reason: classification.reason ?? defaultReason(for: riskLevel, protectedOperation: protectedOperation, mode: mode)
        )

        switch mode {
        case .open:
            if riskLevel == .blocked {
                return baseDecision.withReason(baseDecision.reason ?? "Action blocked by policy")
            }
            return PolicyDecision(
                allowed: true,
                riskLevel: riskLevel,
                protectedOperation: protectedOperation,
                appProtectionProfile: appProtectionProfile,
                blockedByPolicy: false,
                surface: context.surface,
                policyMode: mode,
                requiresApproval: false,
                reason: baseDecision.reason
            )

        case .confirmRisky:
            return baseDecision

        case .lockedDown:
            if riskLevel == .low {
                return PolicyDecision(
                    allowed: true,
                    riskLevel: riskLevel,
                    protectedOperation: protectedOperation,
                    appProtectionProfile: appProtectionProfile,
                    blockedByPolicy: false,
                    surface: context.surface,
                    policyMode: mode,
                    requiresApproval: false,
                    reason: nil
                )
            }
            return PolicyDecision(
                allowed: false,
                riskLevel: riskLevel,
                protectedOperation: protectedOperation,
                appProtectionProfile: appProtectionProfile,
                blockedByPolicy: true,
                surface: context.surface,
                policyMode: mode,
                requiresApproval: false,
                reason: "Action blocked by locked-down policy"
            )
        }
    }

    public static func defaultMode() -> PolicyMode {
        guard let raw = ProcessInfo.processInfo.environment["ORACLE_OS_POLICY_MODE"] else {
            return .confirmRisky
        }
        return PolicyMode(rawValue: raw) ?? .confirmRisky
    }

    private func defaultReason(
        for riskLevel: RiskLevel,
        protectedOperation: ProtectedOperation?,
        mode: PolicyMode
    ) -> String? {
        switch riskLevel {
        case .low:
            return nil
        case .risky:
            return "Action requires approval in \(mode.rawValue) mode"
        case .blocked:
            if let protectedOperation {
                return "Action blocked by policy: \(protectedOperation.rawValue)"
            }
            return "Action blocked by policy"
        }
    }
}
