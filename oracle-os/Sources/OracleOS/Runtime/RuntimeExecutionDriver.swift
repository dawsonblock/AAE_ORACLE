import Foundation
import Combine

/// Bridges the legacy AgentLoop execution path to the new IntentAPI spine.
///
/// MIGRATION STATUS:
///   - Legacy path: `init(runtime:surface:rawActionExecutor:)` — calls performAction (deprecated)
///   - New path:    `init(intentAPI:surface:rawActionExecutor:)` — translates ActionIntent → Intent → submitIntent
///
/// When AgentLoop is fully narrowed, the legacy init can be removed.
@MainActor
public final class RuntimeExecutionDriver: AgentExecutionDriver {
    // LEGACY: remove when AgentLoop is converted to submitIntent path
    private let runtime: RuntimeOrchestrator
    private let surface: RuntimeSurface
    private let rawActionExecutor: @MainActor (ActionIntent) -> ToolResult

    // NEW: IntentAPI-based path (preferred)
    private let intentAPI: (any IntentAPI)?

    /// LEGACY init — routes through performAction (deprecated).
    @available(*, deprecated, message: "Use init(intentAPI:surface:rawActionExecutor:) and route through IntentAPI.submitIntent instead.")
    public init(
        runtime: RuntimeOrchestrator,
        surface: RuntimeSurface = .recipe,
        rawActionExecutor: @escaping @MainActor (ActionIntent) -> ToolResult
    ) {
        self.runtime = runtime
        self.surface = surface
        self.rawActionExecutor = rawActionExecutor
        self.intentAPI = nil
    }

    /// NEW preferred init — translates ActionIntent to Intent and submits via IntentAPI.
    /// This is a pure translator: it converts external input into Intent and forwards it.
    public init(
        intentAPI: any IntentAPI,
        legacyRuntime: RuntimeOrchestrator,
        surface: RuntimeSurface = .recipe,
        rawActionExecutor: @escaping @MainActor (ActionIntent) -> ToolResult
    ) {
        self.intentAPI = intentAPI
        self.runtime = legacyRuntime
        self.surface = surface
        self.rawActionExecutor = rawActionExecutor
    }

    public func execute(
        intent: ActionIntent,
        plannerDecision: PlannerDecision,
        selectedCandidate: ElementCandidate?
    ) -> ToolResult {
        // New path: if intentAPI is set, translate ActionIntent → Intent and submit
        if let api = intentAPI {
            return executeViaIntentAPI(api, intent: intent, plannerDecision: plannerDecision)
        }

        // LEGACY path: route through performAction (deprecated, to be removed)
        return executeLegacy(intent: intent, plannerDecision: plannerDecision, selectedCandidate: selectedCandidate)
    }

    // MARK: - New IntentAPI translation path

    /// Translates ActionIntent to the typed Intent model and submits via IntentAPI.
    /// This is the approved path — no direct executor calls.
    private func executeViaIntentAPI(
        _ api: any IntentAPI,
        intent: ActionIntent,
        plannerDecision: PlannerDecision
    ) -> ToolResult {
        let domain: IntentDomain = intent.agentKind == .code ? .code :
            (intent.agentKind == .mixed ? .system : .ui)

        let typedIntent = Intent(
            domain: domain,
            objective: intent.name,
            metadata: ["query": intent.query ?? intent.text ?? intent.name]
        )

        // Submit intent via API — the sole approved execution gateway
        var result: ToolResult = ToolResult(success: false, error: "IntentAPI submission pending")
        let group = DispatchGroup()
        group.enter()
        Task { @MainActor in
            do {
                let response = try await api.submitIntent(typedIntent)
                result = ToolResult(
                    success: response.outcome == .success || response.outcome == .skipped,
                    data: ["summary": response.summary, "cycleID": response.cycleID.uuidString],
                    error: response.outcome == .failed ? response.summary : nil
                )
            } catch {
                result = ToolResult(success: false, error: error.localizedDescription)
            }
            group.leave()
        }
        group.wait()
        return result
    }

    // MARK: - Legacy path (deprecated)

    private func executeLegacy(
        intent: ActionIntent,
        plannerDecision: PlannerDecision,
        selectedCandidate: ElementCandidate?
    ) -> ToolResult {
        runtime.performAction(
            surface: surface,
            taskID: nil,
            toolName: "agent_loop",
            intent: intent,
            selectedElementID: selectedCandidate?.element.id,
            selectedElementLabel: selectedCandidate?.element.label,
            candidateScore: selectedCandidate?.score,
            candidateReasons: selectedCandidate?.reasons ?? [],
            candidateAmbiguityScore: selectedCandidate?.ambiguityScore,
            plannerSource: plannerDecision.source.rawValue,
            plannerFamily: plannerDecision.plannerFamily.rawValue,
            pathEdgeIDs: plannerDecision.pathEdgeIDs,
            currentEdgeID: plannerDecision.currentEdgeID,
            recoveryTagged: plannerDecision.recoveryTagged,
            recoveryStrategy: plannerDecision.recoveryStrategy,
            recoverySource: plannerDecision.recoverySource,
            projectMemoryRefs: plannerDecision.projectMemoryRefs.map(\.path),
            experimentID: plannerDecision.experimentSpec?.id,
            candidateID: plannerDecision.experimentCandidateID,
            sandboxPath: plannerDecision.experimentSandboxPath,
            selectedCandidate: plannerDecision.selectedExperimentCandidate,
            experimentOutcome: plannerDecision.experimentOutcome ?? (plannerDecision.executionMode == .experiment ? "requested" : nil),
            architectureFindings: plannerDecision.architectureFindings.map(\.title),
            refactorProposalID: plannerDecision.refactorProposalID,
            knowledgeTier: plannerDecision.knowledgeTier
        ) {
            // LEGACY: This closure runs in a non-@MainActor context; we know we're on main actor
            // so assumeIsolated is safe here. Remove when executeLegacy is deleted.
            MainActor.assumeIsolated {
                if intent.agentKind == .code {
                    CodeActionGateway(context: self.runtime.context).execute(intent)
                } else {
                    self.rawActionExecutor(intent)
                }
            }
        }
    }
}
