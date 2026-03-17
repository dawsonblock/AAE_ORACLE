import Foundation
import Testing
@testable import OracleOS

@MainActor
@Suite("Runtime Coordinators")
struct RuntimeCoordinatorTests {
    @Test("State coordinator builds host and browser state bundle")
    func stateCoordinatorBuildsHostAndBrowserBundle() {
        let observation = Observation(
            app: "Google Chrome",
            windowTitle: "Sign in - Example",
            url: "https://example.com/login",
            focusedElementID: "signin",
            elements: [
                UnifiedElement(
                    id: "signin",
                    source: .cdp,
                    role: "button",
                    label: "Sign in",
                    confidence: 0.98
                ),
            ]
        )
        let provider = StaticObservationProvider(observation: observation)
        let host = makeAutomationHost()
        let coordinator = StateCoordinator(
            observationProvider: provider,
            repositoryIndexer: RepositoryIndexer(),
            automationHost: host,
            browserPageStateBuilder: BrowserPageStateBuilder(controller: BrowserController())
        )

        let bundle = coordinator.buildState(
            taskContext: TaskContext.from(goal: Goal(description: "click sign in"), workspaceRoot: nil),
            lastAction: nil as ActionIntent?
        )

        #expect(bundle.hostSnapshot?.activeApplication?.localizedName == "Google Chrome")
        #expect(bundle.hostSnapshot?.windows.first?.title == "Sign in - Example")
        #expect(bundle.browserSession?.page?.domain == "example.com")
        #expect(bundle.browserSession?.available == true)
    }

    @Test("Runtime diagnostics builder includes host and browser snapshots")
    func runtimeDiagnosticsBuilderIncludesHostAndBrowserSnapshots() {
        let graphStore = GraphStore(databaseURL: makeTempGraphURL())
        let hostSnapshot = HostSnapshot(
            activeApplication: HostApplicationSnapshot(
                id: "chrome",
                bundleIdentifier: "com.google.Chrome",
                processIdentifier: 99,
                localizedName: "Google Chrome",
                frontmost: true
            ),
            windows: [
                HostWindowSnapshot(
                    id: "chrome|login",
                    appName: "Google Chrome",
                    title: "Sign in",
                    frame: nil,
                    focused: true,
                    elementCount: 12
                ),
            ],
            menus: [
                HostMenuItemSnapshot(id: "file", title: "File", path: "File"),
            ],
            dialog: HostDialogSnapshot(id: "dlg", title: "Confirm", message: "Continue?", buttonLabels: ["OK", "Cancel"]),
            capture: HostCaptureSnapshot(width: 1280, height: 720, windowTitle: "Sign in"),
            permissions: HostPermissionsSnapshot(accessibilityGranted: true, screenRecordingGranted: false),
            snapshotID: "snapshot-1"
        )
        let browserSession = BrowserSession(
            appName: "Google Chrome",
            page: PageSnapshot(
                browserApp: "Google Chrome",
                title: "Sign in",
                url: "https://example.com/login",
                domain: "example.com",
                simplifiedText: "Sign in Email Password",
                indexedElements: [
                    PageIndexedElement(
                        id: "signin",
                        index: 1,
                        role: "button",
                        label: "Sign in",
                        value: nil,
                        domID: "signin",
                        tag: "button",
                        className: nil,
                        frame: nil,
                        focused: false,
                        enabled: true,
                        visible: true
                    ),
                ]
            ),
            available: true
        )

        let diagnostics = RuntimeDiagnosticsBuilder().build(
            graphStore: graphStore,
            traceEvents: [],
            hostSnapshot: hostSnapshot,
            browserSession: browserSession
        )

        #expect(diagnostics.host?.activeApplication == "Google Chrome")
        #expect(diagnostics.host?.menuCount == 1)
        #expect(diagnostics.browser?.domain == "example.com")
        #expect(diagnostics.browser?.indexedElementCount == 1)
    }

    @Test("Decision coordinator rejects malformed workflow decisions")
    func decisionCoordinatorRejectsMalformedWorkflowDecision() {
        let decision = PlannerDecision(
            agentKind: .os,
            plannerFamily: .os,
            stepPhase: .operatingSystem,
            actionContract: ActionContract(
                id: "click|AXButton|Compose|query",
                skillName: "click",
                targetRole: "AXButton",
                targetLabel: "Compose",
                locatorStrategy: "query"
            ),
            source: .workflow
        )

        let hardened = DecisionCoordinator.harden(
            decision: decision,
            taskContext: TaskContext.from(goal: Goal(description: "open gmail compose"), workspaceRoot: nil)
        )

        #expect(hardened == nil)
    }

    @Test("Decision coordinator adds fallback reason to exploration decisions")
    func decisionCoordinatorAddsExplorationFallbackReason() {
        let decision = PlannerDecision(
            agentKind: .os,
            plannerFamily: .os,
            stepPhase: .operatingSystem,
            actionContract: ActionContract(
                id: "click|AXButton|Compose|query",
                skillName: "click",
                targetRole: "AXButton",
                targetLabel: "Compose",
                locatorStrategy: "query"
            ),
            source: .exploration,
            fallbackReason: nil,
            notes: ["bounded exploration"]
        )

        let hardened = DecisionCoordinator.harden(
            decision: decision,
            taskContext: TaskContext.from(goal: Goal(description: "open gmail compose"), workspaceRoot: nil)
        )

        #expect(hardened?.source == .exploration)
        #expect(hardened?.fallbackReason?.isEmpty == false)
        #expect(hardened?.notes.contains("decision coordinator added explicit exploration fallback reason") == true)
    }

    private func makeAutomationHost() -> AutomationHost {
        let applications = StubApplicationService()
        let windows = StubWindowService()
        let menus = StubMenuService()
        let dialogs = StubDialogService()
        let capture = StubCaptureService()
        let permissions = PermissionService()
        let snapshots = SnapshotService(
            applications: applications,
            windows: windows,
            menus: menus,
            dialogs: dialogs,
            capture: capture,
            permissions: permissions
        )
        return AutomationHost(
            applications: applications,
            windows: windows,
            menus: menus,
            dialogs: dialogs,
            processes: ProcessService(),
            screenCapture: capture,
            snapshots: snapshots,
            permissions: permissions
        )
    }

    private func makeTempGraphURL() -> URL {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        return root.appendingPathComponent("graph.sqlite3", isDirectory: false)
    }
}

@MainActor
private final class StaticObservationProvider: ObservationProvider {
    private let observation: Observation

    init(observation: Observation) {
        self.observation = observation
    }

    func observe() -> Observation {
        observation
    }
}

@MainActor
private final class StubApplicationService: ApplicationServicing {
    func runningApplications() -> [HostApplicationSnapshot] {
        [frontmostApplication()].compactMap { $0 }
    }

    func frontmostApplication() -> HostApplicationSnapshot? {
        HostApplicationSnapshot(
            id: "chrome",
            bundleIdentifier: "com.google.Chrome",
            processIdentifier: 42,
            localizedName: "Google Chrome",
            frontmost: true
        )
    }

    func activateApplication(named name: String) -> Bool { true }
}

@MainActor
private final class StubWindowService: WindowServicing {
    func focusedWindow(appName _: String?) -> HostWindowSnapshot? {
        visibleWindows(appName: nil).first
    }

    func visibleWindows(appName _: String?) -> [HostWindowSnapshot] {
        [
            HostWindowSnapshot(
                id: "chrome|signin",
                appName: "Google Chrome",
                title: "Sign in - Example",
                frame: nil,
                focused: true,
                elementCount: 12
            ),
        ]
    }
}

@MainActor
private final class StubMenuService: MenuServicing {
    func menuItems(appName _: String?) -> [HostMenuItemSnapshot] {
        [HostMenuItemSnapshot(id: "file", title: "File", path: "File")]
    }
}

@MainActor
private final class StubDialogService: DialogServicing {
    func activeDialog(appName _: String?) -> HostDialogSnapshot? { nil }
}

@MainActor
private final class StubCaptureService: CaptureServicing {
    func captureFrontmost(appName _: String?) -> HostCaptureSnapshot? {
        HostCaptureSnapshot(width: 1280, height: 720, windowTitle: "Sign in - Example")
    }
}
