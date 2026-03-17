import Foundation
import Testing
@testable import OracleOS

@MainActor
@Suite("Safe Runtime")
struct SafeRuntimeTests {

    @Test("Policy allows low-risk focus in confirm-risky mode")
    func policyAllowsLowRiskFocus() {
        let engine = PolicyEngine(mode: .confirmRisky)
        let decision = engine.evaluate(
            intent: .focus(app: "Finder"),
            context: PolicyEvaluationContext(surface: .mcp, toolName: "oracle_focus", appName: "Finder")
        )

        #expect(decision.allowed)
        #expect(decision.requiresApproval == false)
        #expect(decision.blockedByPolicy == false)
    }

    @Test("Policy requires approval for send actions in browser contexts")
    func policyRequiresApprovalForSend() {
        let engine = PolicyEngine(mode: .confirmRisky)
        let intent = ActionIntent.click(app: "Google Chrome", query: "Send")
        let decision = engine.evaluate(
            intent: intent,
            context: PolicyEvaluationContext(surface: .mcp, toolName: "oracle_click", appName: "Google Chrome")
        )

        #expect(decision.allowed == false)
        #expect(decision.requiresApproval)
        #expect(decision.protectedOperation == .send)
        #expect(decision.blockedByPolicy == false)
    }

    @Test("Policy blocks terminal interaction by default")
    func policyBlocksTerminalControl() {
        let engine = PolicyEngine(mode: .confirmRisky)
        let decision = engine.evaluate(
            intent: .press(app: "Terminal", key: "return"),
            context: PolicyEvaluationContext(surface: .cli, toolName: "oracle_press", appName: "Terminal")
        )

        #expect(decision.allowed == false)
        #expect(decision.blockedByPolicy)
        #expect(decision.protectedOperation == .terminalControl)
    }

    @Test("Approval receipts are single use")
    func approvalReceiptsSingleUse() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let store = ApprovalStore(rootDirectory: root)
        let request = ApprovalRequest(
            surface: .controller,
            toolName: "oracle_click",
            appName: "Google Chrome",
            displayTitle: "Click Send",
            reason: "Action requires approval",
            riskLevel: .risky,
            protectedOperation: .send,
            actionFingerprint: "fingerprint-send",
            appProtectionProfile: .confirmRisky
        )

        _ = try store.createRequest(request)
        _ = try store.approve(requestID: request.id)

        let firstReceipt = store.consumeApprovedReceipt(requestID: request.id, actionFingerprint: "fingerprint-send")
        let secondReceipt = store.consumeApprovedReceipt(requestID: request.id, actionFingerprint: "fingerprint-send")

        #expect(firstReceipt != nil)
        #expect(firstReceipt?.consumed == true)
        #expect(secondReceipt == nil)
    }

    @Test("Runtime fails closed when risky action has no controller approval path")
    func runtimeFailsClosedWithoutController() {
        let runtime = makeRuntime()
        let result = runtime.performAction(
            surface: .mcp,
            taskID: "test-task",
            toolName: "oracle_click",
            intent: .click(app: "Google Chrome", query: "Send")
        ) {
            ToolResult(success: true, data: ["method": "synthetic"])
        }

        #expect(result.success == false)
        #expect(result.data?["approval_status"] as? String == "unavailable")
        #expect((result.data?["policy_decision"] as? [String: Any])?["requires_approval"] as? Bool == true)
    }

    @Test("Runtime creates pending approval when controller heartbeat is active")
    func runtimeCreatesPendingApproval() {
        let runtime = makeRuntime(controllerConnected: true)
        let result = runtime.performAction(
            surface: .mcp,
            taskID: "test-task",
            toolName: "oracle_click",
            intent: .click(app: "Google Chrome", query: "Send")
        ) {
            ToolResult(success: true, data: ["method": "synthetic"])
        }

        #expect(result.success == false)
        #expect(result.data?["approval_status"] as? String == ApprovalStatus.pending.rawValue)
        #expect((result.data?["approval_request_id"] as? String)?.isEmpty == false)
    }

    @Test("Verified runtime action records graph transition")
    func verifiedRuntimeActionRecordsGraphTransition() {
        let (runtime, graphStore) = makeRuntimeWithGraph()

        let result = runtime.performAction(
            surface: .mcp,
            taskID: "test-task",
            toolName: "oracle_focus",
            intent: .focus(app: "Finder")
        ) {
            ToolResult(success: true, data: ["method": "synthetic-focus"])
        }

        #expect(result.success == false)
        #expect(graphStore.allCandidateEdges().count == 1)
        #expect(graphStore.allCandidateEdges().first?.attempts == 1)
        #expect(graphStore.allCandidateEdges().first?.successes == 0)
    }

    @Test("Failed verified runtime action records graph failure")
    func failedRuntimeActionRecordsGraphFailure() {
        let (runtime, graphStore) = makeRuntimeWithGraph()

        let result = runtime.performAction(
            surface: .mcp,
            taskID: "test-task",
            toolName: "oracle_click",
            intent: .click(app: "Finder", query: "Missing")
        ) {
            ToolResult(success: false, error: "not found")
        }

        #expect(result.success == false)
        #expect(graphStore.allCandidateEdges().count == 1)
        #expect((graphStore.allCandidateEdges().first?.failureHistogram[FailureClass.elementNotFound.rawValue] ?? 0) >= 1)
    }

    private func makeRuntime(controllerConnected: Bool = false) -> RuntimeOrchestrator {
        makeRuntimeWithGraph(controllerConnected: controllerConnected).runtime
    }

    private func makeRuntimeWithGraph(controllerConnected: Bool = false) -> (runtime: RuntimeOrchestrator, graphStore: GraphStore) {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let traceRecorder = TraceRecorder()
        let traceStore = ExperienceStore(directoryURL: root.appendingPathComponent("traces", isDirectory: true))
        let artifactWriter = FailureArtifactWriter(baseURL: root.appendingPathComponent("artifacts", isDirectory: true))
        let approvalStore = ApprovalStore(rootDirectory: root.appendingPathComponent("approvals", isDirectory: true))
        let graphStore = GraphStore(databaseURL: root.appendingPathComponent("graph.sqlite3"))

        if controllerConnected {
            approvalStore.writeControllerHeartbeat(sessionID: "controller-test")
        }

        let context = RuntimeContext(
            config: .live(),
            traceRecorder: traceRecorder,
            traceStore: traceStore,
            artifactWriter: artifactWriter,
            verifiedExecutor: VerifiedActionExecutor(
                traceRecorder: traceRecorder,
                traceStore: traceStore,
                artifactWriter: artifactWriter,
                graphStore: graphStore
            ),
            policyEngine: PolicyEngine(mode: .confirmRisky),
            approvalStore: approvalStore,
            graphStore: graphStore
        )

        return (RuntimeOrchestrator(context: context), graphStore)
    }
}
