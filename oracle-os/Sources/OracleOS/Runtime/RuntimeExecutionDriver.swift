import Foundation

/// Bridges AgentLoop execution to the IntentAPI spine.
@MainActor
public final class RuntimeExecutionDriver: AgentExecutionDriver {
    private final class ToolResultBox: @unchecked Sendable {
        var value: ToolResult

        init(_ value: ToolResult) {
            self.value = value
        }
    }

    private let surface: RuntimeSurface
    private let intentAPI: any IntentAPI

    public init(
        intentAPI: any IntentAPI,
        surface: RuntimeSurface = .recipe
    ) {
        self.intentAPI = intentAPI
        self.surface = surface
    }

    public func execute(
        intent: ActionIntent,
        plannerDecision: PlannerDecision,
        selectedCandidate: ElementCandidate?
    ) -> ToolResult {
        executeViaIntentAPI(intentAPI, intent: intent, plannerDecision: plannerDecision, selectedCandidate: selectedCandidate)
    }

    private func executeViaIntentAPI(
        _ api: any IntentAPI,
        intent: ActionIntent,
        plannerDecision: PlannerDecision,
        selectedCandidate: ElementCandidate?
    ) -> ToolResult {
        let domain: IntentDomain = intent.agentKind == .code ? .code :
            (intent.agentKind == .mixed ? .system : .ui)
        let surfaceValue = surface.rawValue

        let typedIntent = Intent(
            domain: domain,
            objective: intent.name,
            metadata: [
                "query": intent.query ?? intent.text ?? intent.name,
                "surface": surfaceValue,
                "plannerSource": plannerDecision.source.rawValue,
                "plannerFamily": plannerDecision.plannerFamily.rawValue,
                "selectedElementID": selectedCandidate?.element.id ?? "",
                "workspaceRoot": intent.workspaceRoot ?? "",
                "workspaceRelativePath": intent.workspaceRelativePath ?? "",
                "commandCategory": intent.commandCategory ?? "",
            ]
        )

        let resultBox = ToolResultBox(ToolResult(success: false, error: "IntentAPI submission pending"))
        let semaphore = DispatchSemaphore(value: 0)
        Task.detached {
            do {
                let response = try await api.submitIntent(typedIntent)
                let actionResult = ActionResult(
                    success: response.outcome == .success || response.outcome == .skipped,
                    verified: response.outcome != .failed,
                    message: response.summary,
                    surface: surfaceValue,
                    executedThroughExecutor: true
                )
                resultBox.value = ToolResult(
                    success: response.outcome == .success || response.outcome == .skipped,
                    data: [
                        "summary": response.summary,
                        "cycleID": response.cycleID.uuidString,
                        "action_result": actionResult.toDict(),
                    ],
                    error: response.outcome == .failed ? response.summary : nil
                )
            } catch {
                resultBox.value = ToolResult(success: false, error: error.localizedDescription)
            }
            semaphore.signal()
        }
        semaphore.wait()
        return resultBox.value
    }
}
