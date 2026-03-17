import Foundation
import Testing
@testable import OracleOS

@MainActor
@Suite("Graph Aware Loop")
struct GraphAwareLoopTests {

    @Test("GraphStore persists eligible stable edges and action contracts")
    func graphStorePersistsStableEdges() {
        let dbURL = makeTempGraphURL()
        let store = GraphStore(databaseURL: dbURL)
        let fromState = planningState(
            id: "chrome|gmail|browse",
            appID: "Google Chrome",
            domain: "mail.google.com",
            taskPhase: "browse"
        )
        let toState = planningState(
            id: "chrome|gmail|compose",
            appID: "Google Chrome",
            domain: "mail.google.com",
            taskPhase: "compose"
        )
        let contract = ActionContract(
            id: "click|AXButton|Compose|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose",
            locatorStrategy: "query"
        )

        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: fromState.id,
                    to: toState.id,
                    actionContractID: contract.id,
                    verified: true
                ),
                actionContract: contract,
                fromState: fromState,
                toState: toState
            )
        }

        let promoted = store.promoteEligibleEdges()
        #expect(promoted.count == 1)

        let reopened = GraphStore(databaseURL: dbURL)
        #expect(reopened.actionContract(for: contract.id)?.targetLabel == "Compose")
        #expect(reopened.outgoingStableEdges(from: fromState.id).count == 1)
        #expect(reopened.planningState(for: toState.id)?.taskPhase == "compose")
    }

    @Test("GraphStore records failures without promoting edge")
    func graphStoreRecordsFailureWithoutPromotion() {
        let store = GraphStore(databaseURL: makeTempGraphURL())
        let state = planningState(
            id: "finder|rename",
            appID: "Finder",
            domain: nil,
            taskPhase: "browse"
        )
        let contract = ActionContract(
            id: "click|AXButton|Rename|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Rename",
            locatorStrategy: "query"
        )

        store.recordFailure(
            state: state,
            actionContract: contract,
            failure: .elementNotFound
        )
        _ = store.promoteEligibleEdges()

        #expect(store.allStableEdges().isEmpty)
        #expect(store.allCandidateEdges().first?.failureHistogram[FailureClass.elementNotFound.rawValue] == 1)
    }

    @Test("Promotion freezes when global verified success rate is too low")
    func promotionFreezeWhenGlobalSuccessRateLow() {
        let store = GraphStore(databaseURL: makeTempGraphURL())
        let goodFrom = planningState(id: "good|from", appID: "Finder", domain: nil, taskPhase: "browse")
        let goodTo = planningState(id: "good|to", appID: "Finder", domain: nil, taskPhase: "rename")
        let goodContract = ActionContract(
            id: "click|AXButton|Rename|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Rename",
            locatorStrategy: "query"
        )

        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: goodFrom.id,
                    to: goodTo.id,
                    actionContractID: goodContract.id,
                    verified: true
                ),
                actionContract: goodContract,
                fromState: goodFrom,
                toState: goodTo
            )
        }

        let failureState = planningState(id: "bad|state", appID: "Finder", domain: nil, taskPhase: "browse")
        let failureContract = ActionContract(
            id: "click|AXButton|Delete|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Delete",
            locatorStrategy: "query"
        )
        for _ in 0..<6 {
            store.recordFailure(
                state: failureState,
                actionContract: failureContract,
                failure: .actionFailed
            )
        }

        let promoted = store.promoteEligibleEdges()
        #expect(promoted.isEmpty)
        #expect(store.allStableEdges().isEmpty)
    }

    @Test("Stable edges demote after repeated failures")
    func stableEdgesDemoteAfterFailures() {
        let store = GraphStore(databaseURL: makeTempGraphURL())
        let fromState = planningState(id: "gmail|browse", appID: "Google Chrome", domain: "mail.google.com", taskPhase: "browse")
        let toState = planningState(id: "gmail|compose", appID: "Google Chrome", domain: "mail.google.com", taskPhase: "compose")
        let contract = ActionContract(
            id: "click|AXButton|Compose|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose",
            locatorStrategy: "query"
        )

        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: fromState.id,
                    to: toState.id,
                    actionContractID: contract.id,
                    verified: true
                ),
                actionContract: contract,
                fromState: fromState,
                toState: toState
            )
        }
        _ = store.promoteEligibleEdges()
        #expect(store.allStableEdges().count == 1)

        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: fromState.id,
                    to: toState.id,
                    actionContractID: contract.id,
                    verified: false,
                    failureClass: .verificationFailed
                ),
                actionContract: contract,
                fromState: fromState,
                toState: toState
            )
        }

        let removed = store.pruneOrDemoteEdges()
        #expect(removed == [store.allCandidateEdges().first?.edgeID].compactMap { $0 })
        #expect(store.allStableEdges().isEmpty)
    }

    @Test("ClickSkill fails on ambiguous targets instead of picking first element")
    func clickSkillFailsOnAmbiguousTargets() {
        let observation = Observation(
            app: "Google Chrome",
            windowTitle: "Compose - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox?compose=new",
            focusedElementID: nil,
            elements: [
                UnifiedElement(id: "send-primary", source: .ax, role: "AXButton", label: "Send", confidence: 0.95),
                UnifiedElement(id: "send-secondary", source: .ax, role: "AXButton", label: "Send", confidence: 0.94),
            ]
        )
        let state = WorldState(observation: observation)
        let skill = ClickSkill()

        do {
            _ = try skill.resolve(
                query: ElementQuery(text: "Send", clickable: true),
                state: state,
                memoryStore: UnifiedMemoryStore()
            )
            Issue.record("Expected ambiguous target error")
        } catch let error as SkillResolutionError {
            #expect(error.failureClass == .elementAmbiguous)
        } catch {
            Issue.record("Unexpected error: \(error)")
        }
    }

    @Test("AgentLoop prefers stable graph path when available")
    func agentLoopPrefersStableGraph() async {
        let abstraction = StateAbstraction()
        let inboxObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Inbox - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox",
            focusedElementID: "compose",
            elements: [
                UnifiedElement(id: "compose", source: .ax, role: "AXButton", label: "Compose", focused: true, confidence: 0.98),
            ]
        )
        let composeObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Compose - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox?compose=new",
            focusedElementID: "body",
            elements: [
                UnifiedElement(id: "body", source: .ax, role: "AXTextArea", label: "Message Body", focused: true, confidence: 0.95),
                UnifiedElement(id: "send", source: .ax, role: "AXButton", label: "Send", confidence: 0.91),
            ]
        )
        let fromState = abstraction.abstract(
            observation: inboxObservation,
            observationHash: ObservationHash.hash(inboxObservation)
        )
        let toState = abstraction.abstract(
            observation: composeObservation,
            observationHash: ObservationHash.hash(composeObservation)
        )
        let store = GraphStore(databaseURL: makeTempGraphURL())
        let contract = ActionContract(
            id: "click|AXButton|Compose|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose",
            locatorStrategy: "query"
        )
        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: fromState.id,
                    to: toState.id,
                    actionContractID: contract.id,
                    verified: true
                ),
                actionContract: contract,
                fromState: fromState,
                toState: toState
            )
        }
        _ = store.promoteEligibleEdges()

        let provider = StubObservationProvider([inboxObservation, composeObservation])
        let driver = RecordingExecutionDriver { _, _, _ in
            ToolResult(success: true, data: [
                "action_result": ActionResult(success: true, verified: true).toDict(),
            ])
        }
        let loop = AgentLoop(
            orchestrator: NoOpIntentAPI(),
            observationProvider: provider,
            executionDriver: driver,
            stateAbstraction: abstraction,
            planner: MainPlanner(),
            graphStore: store,
            policyEngine: PolicyEngine(mode: .confirmRisky),
            recoveryEngine: RecoveryEngine(),
            memoryStore: UnifiedMemoryStore()
        )

        let outcome = await loop.run(
            goal: Goal(
                description: "open gmail compose",
                targetApp: "Google Chrome",
                targetDomain: "mail.google.com",
                targetTaskPhase: "compose"
            )
        )

        #expect(outcome.reason == .goalAchieved)
        #expect(driver.decisions.first?.source == .stableGraph)
        #expect(driver.decisions.first?.fallbackReason == "workflow retrieval did not yield a reusable plan")
        #expect(driver.intents.first?.domID == "compose")
    }

    @Test("AgentLoop falls back to exploration when no graph path exists")
    func agentLoopFallsBackToExploration() async {
        let abstraction = StateAbstraction()
        let finderObservation = Observation(
            app: "Finder",
            windowTitle: "Finder",
            url: nil,
            focusedElementID: "rename",
            elements: [
                UnifiedElement(id: "rename", source: .ax, role: "AXButton", label: "Rename", focused: true, confidence: 0.96),
            ]
        )
        let renamedObservation = Observation(
            app: "Finder",
            windowTitle: "Finder",
            url: nil,
            focusedElementID: "save",
            elements: [
                UnifiedElement(id: "save", source: .ax, role: "AXButton", label: "Save", focused: true, confidence: 0.94),
            ]
        )
        let provider = StubObservationProvider([finderObservation, renamedObservation])
        let driver = RecordingExecutionDriver { _, decision, _ in
            #expect(decision.source == .exploration)
            return ToolResult(success: true, data: [
                "action_result": ActionResult(success: true, verified: true).toDict(),
            ])
        }
        let loop = AgentLoop(
            orchestrator: NoOpIntentAPI(),
            observationProvider: provider,
            executionDriver: driver,
            stateAbstraction: abstraction,
            planner: MainPlanner(),
            graphStore: GraphStore(databaseURL: makeTempGraphURL()),
            policyEngine: PolicyEngine(mode: .confirmRisky),
            recoveryEngine: RecoveryEngine(),
            memoryStore: UnifiedMemoryStore()
        )

        let outcome = await loop.run(
            goal: Goal(
                description: "rename file in finder",
                targetApp: "Finder",
                targetTaskPhase: "save"
            )
        )

        #expect(outcome.reason == .goalAchieved)
        #expect(driver.decisions.first?.source == .exploration)
    }

    @Test("AgentLoop recognizes goal reached immediately after a successful step")
    func agentLoopRecognizesGoalAfterSuccessfulStep() async {
        let abstraction = StateAbstraction()
        let finderObservation = Observation(
            app: "Finder",
            windowTitle: "Finder",
            url: nil,
            focusedElementID: "rename",
            elements: [
                UnifiedElement(id: "rename", source: .ax, role: "AXButton", label: "Rename", focused: true, confidence: 0.96),
            ]
        )
        let savedObservation = Observation(
            app: "Finder",
            windowTitle: "Finder",
            url: nil,
            focusedElementID: "save",
            elements: [
                UnifiedElement(id: "save", source: .ax, role: "AXButton", label: "Save", focused: true, confidence: 0.97),
            ]
        )
        let provider = StubObservationProvider([finderObservation, savedObservation])
        let driver = RecordingExecutionDriver { _, _, _ in
            ToolResult(success: true, data: [
                "action_result": ActionResult(success: true, verified: true).toDict(),
            ])
        }
        let loop = AgentLoop(
            orchestrator: NoOpIntentAPI(),
            observationProvider: provider,
            executionDriver: driver,
            stateAbstraction: abstraction,
            planner: MainPlanner(),
            graphStore: GraphStore(databaseURL: makeTempGraphURL()),
            policyEngine: PolicyEngine(mode: .confirmRisky),
            recoveryEngine: RecoveryEngine(),
            memoryStore: UnifiedMemoryStore()
        )

        let outcome = await loop.run(
            goal: Goal(
                description: "rename file in finder",
                targetApp: "Finder",
                targetTaskPhase: "save"
            ),
            budget: LoopBudget(maxSteps: 1)
        )

        #expect(outcome.reason == .goalAchieved)
        #expect(outcome.finalWorldState?.observation.focusedElementID == "save")
        #expect(outcome.steps == 1)
    }

    @Test("AgentLoop terminates when exploration budget is exhausted")
    func agentLoopStopsWhenExplorationBudgetExhausted() async {
        let observation = Observation(
            app: "Finder",
            windowTitle: "Finder",
            url: nil,
            focusedElementID: "rename",
            elements: [
                UnifiedElement(id: "rename", source: .ax, role: "AXButton", label: "Rename", focused: true, confidence: 0.96),
            ]
        )
        let provider = StubObservationProvider([observation, observation, observation])
        let driver = RecordingExecutionDriver { _, _, _ in
            Issue.record("Exploration budget should terminate before execution")
            return ToolResult(success: true)
        }
        let loop = AgentLoop(
            orchestrator: NoOpIntentAPI(),
            observationProvider: provider,
            executionDriver: driver,
            stateAbstraction: StateAbstraction(),
            planner: MainPlanner(),
            graphStore: GraphStore(databaseURL: makeTempGraphURL()),
            policyEngine: PolicyEngine(mode: .confirmRisky),
            recoveryEngine: RecoveryEngine(),
            memoryStore: UnifiedMemoryStore()
        )

        let outcome = await loop.run(
            goal: Goal(
                description: "rename file in finder",
                targetApp: "Finder",
                targetTaskPhase: "save"
            ),
            budget: LoopBudget(
                maxSteps: 5,
                maxRecoveries: 1,
                maxConsecutiveExplorationSteps: 0
            )
        )

        #expect(outcome.reason == .explorationBudgetExceeded)
        #expect(driver.intents.isEmpty)
        #expect(outcome.diagnostics.stepSummaries.last?.terminationReason == .explorationBudgetExceeded)
    }

    @Test("AgentLoop terminates approval-gated actions before execution")
    func agentLoopTerminatesApprovalGatedActionsBeforeExecution() async {
        let composeObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Compose - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox?compose=new",
            focusedElementID: "send",
            elements: [
                UnifiedElement(id: "send", source: .ax, role: "AXButton", label: "Send", focused: true, confidence: 0.98),
            ]
        )
        let abstraction = StateAbstraction()
        let fromState = abstraction.abstract(
            observation: composeObservation,
            observationHash: ObservationHash.hash(composeObservation)
        )
        let toState = planningState(
            id: "chrome|gmail|sent",
            appID: "Google Chrome",
            domain: "mail.google.com",
            taskPhase: "sent"
        )
        let store = GraphStore(databaseURL: makeTempGraphURL())
        let contract = ActionContract(
            id: "click|AXButton|Send|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Send",
            locatorStrategy: "query"
        )
        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: fromState.id,
                    to: toState.id,
                    actionContractID: contract.id,
                    verified: true
                ),
                actionContract: contract,
                fromState: fromState,
                toState: toState
            )
        }
        _ = store.promoteEligibleEdges()

        let provider = StubObservationProvider([composeObservation])
        let driver = RecordingExecutionDriver { _, _, _ in
            Issue.record("Policy should block before driver execution")
            return ToolResult(success: true)
        }
        let loop = AgentLoop(
            orchestrator: NoOpIntentAPI(),
            observationProvider: provider,
            executionDriver: driver,
            stateAbstraction: abstraction,
            planner: MainPlanner(),
            graphStore: store,
            policyEngine: PolicyEngine(mode: .confirmRisky),
            recoveryEngine: RecoveryEngine(),
            memoryStore: UnifiedMemoryStore()
        )

        let outcome = await loop.run(
            goal: Goal(
                description: "send gmail message",
                targetApp: "Google Chrome",
                targetDomain: "mail.google.com",
                targetTaskPhase: "sent"
            )
        )

        #expect(outcome.reason == .approvalTimeout)
        #expect(driver.intents.isEmpty)
        #expect(outcome.diagnostics.stepSummaries.last?.policyOutcome == .blocked)
        #expect(outcome.diagnostics.stepSummaries.last?.terminationReason == .approvalTimeout)
    }

    @Test("AgentLoop terminates blocked actions before execution")
    func agentLoopTerminatesBlockedActionsBeforeExecution() async {
        let observation = Observation(
            app: "Terminal",
            windowTitle: "Terminal",
            url: nil,
            focusedElementID: "prompt",
            elements: [
                UnifiedElement(id: "prompt", source: .ax, role: "AXTextArea", label: "Shell Prompt", focused: true, confidence: 0.96),
                UnifiedElement(id: "continue-button", source: .ax, role: "AXButton", label: "Shell Prompt", confidence: 0.94),
            ]
        )
        let driver = RecordingExecutionDriver { _, _, _ in
            Issue.record("Blocked terminal action should not reach the execution driver")
            return ToolResult(success: true)
        }
        let loop = AgentLoop(
            orchestrator: NoOpIntentAPI(),
            observationProvider: StubObservationProvider([observation]),
            executionDriver: driver,
            planner: MainPlanner(),
            graphStore: GraphStore(databaseURL: makeTempGraphURL()),
            policyEngine: PolicyEngine(mode: .confirmRisky),
            recoveryEngine: RecoveryEngine(),
            memoryStore: UnifiedMemoryStore()
        )

        let outcome = await loop.run(
            goal: Goal(
                description: "continue terminal task",
                targetApp: "Terminal",
                targetTaskPhase: "shell"
            )
        )

        #expect(outcome.reason == .policyBlocked)
        #expect(driver.intents.isEmpty)
        #expect(outcome.diagnostics.stepSummaries.last?.policyOutcome == .blocked)
    }

    @Test("AgentLoop invokes recovery after verified failure")
    func agentLoopInvokesRecoveryAfterFailure() async {
        let abstraction = StateAbstraction()
        let inboxObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Inbox - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox",
            focusedElementID: "compose",
            elements: [
                UnifiedElement(id: "compose", source: .ax, role: "AXButton", label: "Compose", focused: true, confidence: 0.98),
            ]
        )
        let composeObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Compose - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox?compose=new",
            focusedElementID: "body",
            elements: [
                UnifiedElement(id: "body", source: .ax, role: "AXTextArea", label: "Message Body", focused: true, confidence: 0.95),
            ]
        )
        let fromState = abstraction.abstract(
            observation: inboxObservation,
            observationHash: ObservationHash.hash(inboxObservation)
        )
        let toState = abstraction.abstract(
            observation: composeObservation,
            observationHash: ObservationHash.hash(composeObservation)
        )
        let store = GraphStore(databaseURL: makeTempGraphURL())
        let contract = ActionContract(
            id: "click|AXButton|Compose|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose",
            locatorStrategy: "query"
        )
        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: fromState.id,
                    to: toState.id,
                    actionContractID: contract.id,
                    verified: true
                ),
                actionContract: contract,
                fromState: fromState,
                toState: toState
            )
        }
        _ = store.promoteEligibleEdges()

        let provider = StubObservationProvider([inboxObservation, inboxObservation, composeObservation])
        let driver = RecordingExecutionDriver { _, decision, _ in
            if decision.source == .recovery {
                return ToolResult(success: true, data: [
                    "action_result": ActionResult(
                        success: true,
                        verified: true,
                        message: "recovery succeeded"
                    ).toDict(),
                ])
            }
            return ToolResult(success: false, data: [
                "action_result": ActionResult(
                    success: false,
                    verified: false,
                    failureClass: FailureClass.wrongFocus.rawValue
                ).toDict(),
            ], error: "wrong focus")
        }
        let loop = AgentLoop(
            orchestrator: NoOpIntentAPI(),
            observationProvider: provider,
            executionDriver: driver,
            stateAbstraction: abstraction,
            planner: MainPlanner(),
            graphStore: store,
            policyEngine: PolicyEngine(mode: .confirmRisky),
            recoveryEngine: RecoveryEngine(),
            memoryStore: UnifiedMemoryStore()
        )

        let outcome = await loop.run(
            goal: Goal(
                description: "open gmail compose",
                targetApp: "Google Chrome",
                targetDomain: "mail.google.com",
                targetTaskPhase: "compose"
            )
        )

        #expect(outcome.reason == .goalAchieved)
        #expect(outcome.recoveries == 1)
        #expect(driver.intents.count == 2)
        #expect(driver.decisions.last?.source == .recovery)
        let recoverySucceeded = outcome.diagnostics.stepSummaries.contains { summary in
            summary.recoveryOutcome == .succeeded && summary.recoveryStrategy == "refocus_app"
        }
        #expect(recoverySucceeded)
    }

    @Test("AgentLoop bounds recovery attempts and terminates after failed recovery")
    func agentLoopBoundsRecoveryAttempts() async {
        let abstraction = StateAbstraction()
        let inboxObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Inbox - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox",
            focusedElementID: "compose",
            elements: [
                UnifiedElement(id: "compose", source: .ax, role: "AXButton", label: "Compose", focused: true, confidence: 0.98),
            ]
        )
        let composeObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Compose - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox?compose=new",
            focusedElementID: "body",
            elements: [
                UnifiedElement(id: "body", source: .ax, role: "AXTextArea", label: "Message Body", focused: true, confidence: 0.95),
            ]
        )
        let fromState = abstraction.abstract(
            observation: inboxObservation,
            observationHash: ObservationHash.hash(inboxObservation)
        )
        let toState = abstraction.abstract(
            observation: composeObservation,
            observationHash: ObservationHash.hash(composeObservation)
        )
        let store = GraphStore(databaseURL: makeTempGraphURL())
        let contract = ActionContract(
            id: "click|AXButton|Compose|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose",
            locatorStrategy: "query"
        )
        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: fromState.id,
                    to: toState.id,
                    actionContractID: contract.id,
                    verified: true
                ),
                actionContract: contract,
                fromState: fromState,
                toState: toState
            )
        }
        _ = store.promoteEligibleEdges()

        let provider = StubObservationProvider([inboxObservation, inboxObservation, composeObservation, composeObservation])
        let driver = RecordingExecutionDriver { _, _, _ in
            ToolResult(success: false, data: [
                "action_result": ActionResult(
                    success: false,
                    verified: false,
                    failureClass: FailureClass.wrongFocus.rawValue
                ).toDict(),
            ], error: "wrong focus")
        }
        let loop = AgentLoop(
            orchestrator: NoOpIntentAPI(),
            observationProvider: provider,
            executionDriver: driver,
            stateAbstraction: abstraction,
            planner: MainPlanner(),
            graphStore: store,
            policyEngine: PolicyEngine(mode: .confirmRisky),
            recoveryEngine: RecoveryEngine(),
            memoryStore: UnifiedMemoryStore()
        )

        let outcome = await loop.run(
            goal: Goal(
                description: "open gmail compose",
                targetApp: "Google Chrome",
                targetDomain: "mail.google.com",
                targetTaskPhase: "compose"
            ),
            budget: LoopBudget(maxRecoveries: 1)
        )

        #expect(outcome.reason == .unrecoverableFailure)
        #expect(outcome.recoveries == 1)
        #expect(driver.intents.count == 2)
        #expect(driver.decisions.last?.source == .recovery)
        let recoveryFailed = outcome.diagnostics.stepSummaries.contains { summary in
            summary.recoveryOutcome == .failed && summary.recoveryStrategy == "refocus_app"
        }
        #expect(recoveryFailed)
    }

    @Test("Blocked runtime actions do not create graph edges")
    func blockedRuntimeActionsDoNotCreateGraphEdges() {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let traceRecorder = TraceRecorder()
        let traceStore = ExperienceStore(directoryURL: root.appendingPathComponent("traces", isDirectory: true))
        let artifactWriter = FailureArtifactWriter(baseURL: root.appendingPathComponent("artifacts", isDirectory: true))
        let approvalStore = ApprovalStore(rootDirectory: root.appendingPathComponent("approvals", isDirectory: true))
        let graphStore = GraphStore(databaseURL: root.appendingPathComponent("graph.sqlite3"))
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
        let runtime = RuntimeOrchestrator(context: context)

        let result = runtime.performAction(
            surface: .mcp,
            toolName: "oracle_click",
            intent: .click(app: "Google Chrome", query: "Send")
        ) {
            ToolResult(success: true, data: ["method": "synthetic"])
        }

        #expect(result.success == false)
        #expect(graphStore.allCandidateEdges().isEmpty)
        #expect(graphStore.allStableEdges().isEmpty)
    }

    @Test("Planner prefers workflow retrieval before stable graph reuse")
    func plannerPrefersWorkflowBeforeStableGraph() {
        let abstraction = StateAbstraction()
        let inboxObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Inbox - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox",
            focusedElementID: "compose",
            elements: [
                UnifiedElement(id: "compose", source: .ax, role: "AXButton", label: "Compose", focused: true, confidence: 0.98),
            ]
        )
        let composeObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Compose - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox?compose=new",
            focusedElementID: "body",
            elements: [
                UnifiedElement(id: "body", source: .ax, role: "AXTextArea", label: "Message Body", focused: true, confidence: 0.95),
            ]
        )
        let fromState = abstraction.abstract(
            observation: inboxObservation,
            observationHash: ObservationHash.hash(inboxObservation)
        )
        let toState = abstraction.abstract(
            observation: composeObservation,
            observationHash: ObservationHash.hash(composeObservation)
        )
        let contract = ActionContract(
            id: "click|AXButton|Compose|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose",
            locatorStrategy: "query"
        )
        let store = GraphStore(databaseURL: makeTempGraphURL())
        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: fromState.id,
                    to: toState.id,
                    actionContractID: contract.id,
                    verified: true
                ),
                actionContract: contract,
                fromState: fromState,
                toState: toState
            )
        }
        _ = store.promoteEligibleEdges()

        let planner = MainPlanner()
        planner.workflowIndex.add(
            WorkflowPlan(
                agentKind: .os,
                goalPattern: "open gmail compose",
                steps: [
                    WorkflowStep(
                        agentKind: .os,
                        stepPhase: .operatingSystem,
                        actionContract: contract,
                        semanticQuery: ElementQuery(
                            text: "Compose",
                            role: "AXButton",
                            clickable: true,
                            visibleOnly: true,
                            app: "Google Chrome"
                        ),
                        fromPlanningStateID: fromState.id.rawValue
                    ),
                ],
                successRate: 0.95,
                sourceTraceRefs: ["trace-1"],
                sourceGraphEdgeRefs: ["edge-1"],
                repeatedTraceSegmentCount: 3,
                replayValidationSuccess: 1,
                promotionStatus: .promoted
            )
        )
        planner.setGoal(
            Goal(
                description: "open gmail compose",
                targetApp: "Google Chrome",
                targetDomain: "mail.google.com",
                targetTaskPhase: "compose"
            )
        )

        let decision = planner.nextStep(
            worldState: WorldState(observation: inboxObservation),
            graphStore: store,
            memoryStore: UnifiedMemoryStore()
        )

        #expect(decision?.source == .workflow)
        #expect(decision?.workflowID != nil)
    }

    @Test("Planner reuses candidate graph edge before exploration")
    func plannerReusesCandidateGraphEdgeBeforeExploration() {
        let abstraction = StateAbstraction()
        let inboxObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Inbox - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox",
            focusedElementID: "compose",
            elements: [
                UnifiedElement(id: "compose", source: .ax, role: "AXButton", label: "Compose", focused: true, confidence: 0.98),
            ]
        )
        let composeObservation = Observation(
            app: "Google Chrome",
            windowTitle: "Compose - Gmail",
            url: "https://mail.google.com/mail/u/0/#inbox?compose=new",
            focusedElementID: "body",
            elements: [
                UnifiedElement(id: "body", source: .ax, role: "AXTextArea", label: "Message Body", focused: true, confidence: 0.95),
            ]
        )
        let fromState = abstraction.abstract(
            observation: inboxObservation,
            observationHash: ObservationHash.hash(inboxObservation)
        )
        let toState = abstraction.abstract(
            observation: composeObservation,
            observationHash: ObservationHash.hash(composeObservation)
        )
        let store = GraphStore(databaseURL: makeTempGraphURL())
        let contract = ActionContract(
            id: "click|AXButton|Compose|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose",
            locatorStrategy: "query"
        )
        for _ in 0..<2 {
            store.recordTransition(
                transition(
                    from: fromState.id,
                    to: toState.id,
                    actionContractID: contract.id,
                    verified: true
                ),
                actionContract: contract,
                fromState: fromState,
                toState: toState
            )
        }

        let planner = MainPlanner()
        planner.setGoal(
            Goal(
                description: "open gmail compose",
                targetApp: "Google Chrome",
                targetDomain: "mail.google.com",
                targetTaskPhase: "compose"
            )
        )

        let decision = planner.nextStep(
            worldState: WorldState(observation: inboxObservation),
            graphStore: store,
            memoryStore: UnifiedMemoryStore()
        )

        #expect(decision?.source == .candidateGraph)
        #expect(decision?.currentEdgeID == store.allCandidateEdges().first?.edgeID)
        #expect(decision?.fallbackReason == "workflow retrieval and stable graph path reuse were unavailable")
        #expect(decision?.graphSearchDiagnostics?.chosenPathEdgeIDs.count == 1)
    }

    @Test("Exploration decisions carry explicit fallback reasons")
    func explorationDecisionCarriesFallbackReason() {
        let planner = MainPlanner()
        planner.setGoal(
            Goal(
                description: "rename file in finder",
                targetApp: "Finder",
                targetTaskPhase: "rename"
            )
        )

        let decision = planner.nextStep(
            worldState: WorldState(
                observation: Observation(
                    app: "Finder",
                    windowTitle: "Finder",
                    url: nil,
                    focusedElementID: "rename",
                    elements: [
                        UnifiedElement(id: "rename", source: .ax, role: "AXButton", label: "Rename", confidence: 0.97),
                    ]
                )
            ),
            graphStore: GraphStore(databaseURL: makeTempGraphURL()),
            memoryStore: UnifiedMemoryStore()
        )

        #expect(decision?.source == .exploration)
        #expect(decision?.fallbackReason == "workflow retrieval, stable graph path reuse, and candidate graph reuse were unavailable")
    }

    @Test("Graph planner returns multi-step stable path before exploration")
    func graphPlannerReturnsMultiStepStablePath() {
        let store = GraphStore(databaseURL: makeTempGraphURL())
        let start = planningState(id: "gmail|inbox", appID: "Google Chrome", domain: "mail.google.com", taskPhase: "browse")
        let middle = planningState(id: "gmail|menu", appID: "Google Chrome", domain: "mail.google.com", taskPhase: "menu")
        let end = planningState(id: "gmail|compose", appID: "Google Chrome", domain: "mail.google.com", taskPhase: "compose")
        let firstContract = ActionContract(
            id: "click|AXButton|ComposeMenu|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose Menu",
            locatorStrategy: "query"
        )
        let secondContract = ActionContract(
            id: "click|AXButton|Compose|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose",
            locatorStrategy: "query"
        )

        for _ in 0..<5 {
            store.recordTransition(
                transition(
                    from: start.id,
                    to: middle.id,
                    actionContractID: firstContract.id,
                    verified: true
                ),
                actionContract: firstContract,
                fromState: start,
                toState: middle
            )
            store.recordTransition(
                transition(
                    from: middle.id,
                    to: end.id,
                    actionContractID: secondContract.id,
                    verified: true
                ),
                actionContract: secondContract,
                fromState: middle,
                toState: end
            )
        }
        _ = store.promoteEligibleEdges()

        let planner = GraphMainPlanner(maxDepth: 6, beamWidth: 5)
        let result = planner.search(
            from: start,
            goal: Goal(
                description: "open gmail compose",
                targetApp: "Google Chrome",
                targetDomain: "mail.google.com",
                targetTaskPhase: "compose",
                preferredAgentKind: .os
            ),
            graphStore: store,
            memoryStore: UnifiedMemoryStore(),
            worldState: WorldState(
                observationHash: "start-hash",
                planningState: start,
                observation: Observation(app: "Google Chrome", windowTitle: "Inbox", url: "https://mail.google.com/mail/u/0/#inbox"),
                repositorySnapshot: nil
            )
        )

        #expect(result?.edges.count == 2)
        #expect(result?.diagnostics.chosenPathEdgeIDs.count == 2)
        #expect(result?.exploredEdgeIDs.isEmpty == false)
    }

    @Test("Workflow promotion policy rejects experiment and recovery evidence")
    func workflowPromotionPolicyRejectsUntrustedEvidence() {
        let policy = WorkflowPromotionPolicy()
        let contract = ActionContract(
            id: "click|AXButton|Compose|query",
            skillName: "click",
            targetRole: "AXButton",
            targetLabel: "Compose",
            locatorStrategy: "query"
        )
        let promoted = WorkflowPlan(
            agentKind: .os,
            goalPattern: "open gmail compose",
            steps: [
                WorkflowStep(
                    agentKind: .os,
                    stepPhase: .operatingSystem,
                    actionContract: contract
                ),
            ],
            successRate: 0.9,
            sourceTraceRefs: ["session1:compose:0", "session2:compose:0", "session3:compose:0"],
            evidenceTiers: [.candidate],
            repeatedTraceSegmentCount: 3,
            replayValidationSuccess: 0.9,
            promotionStatus: .candidate
        )
        let experimental = WorkflowPlan(
            agentKind: .os,
            goalPattern: "open gmail compose",
            steps: [
                WorkflowStep(
                    agentKind: .os,
                    stepPhase: .operatingSystem,
                    actionContract: contract
                ),
            ],
            successRate: 0.95,
            sourceTraceRefs: ["session1:compose:0", "session2:compose:0", "session3:compose:0", "session4:compose:0"],
            evidenceTiers: [.experiment],
            repeatedTraceSegmentCount: 4,
            replayValidationSuccess: 0.9,
            promotionStatus: .candidate
        )

        #expect(policy.shouldPromote(promoted))
        #expect(policy.shouldPromote(experimental) == false)
    }

    private func transition(
        from: PlanningStateID,
        to: PlanningStateID,
        actionContractID: String,
        verified: Bool,
        failureClass: FailureClass? = nil
    ) -> VerifiedTransition {
        VerifiedTransition(
            fromPlanningStateID: from,
            toPlanningStateID: to,
            actionContractID: actionContractID,
            postconditionClass: .elementAppeared,
            verified: verified,
            failureClass: failureClass?.rawValue,
            latencyMs: 120
        )
    }

    private func planningState(
        id: String,
        appID: String,
        domain: String?,
        taskPhase: String?
    ) -> PlanningState {
        PlanningState(
            id: PlanningStateID(rawValue: id),
            clusterKey: StateClusterKey(rawValue: id),
            appID: appID,
            domain: domain,
            windowClass: nil,
            taskPhase: taskPhase,
            focusedRole: "AXButton",
            modalClass: nil,
            navigationClass: domain == nil ? nil : "web",
            controlContext: nil
        )
    }

    private func makeTempGraphURL() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
            .appendingPathComponent("graph.sqlite3", isDirectory: false)
    }
}

@MainActor
private final class StubObservationProvider: ObservationProvider {
    private let observations: [Observation]
    private var index = 0

    init(_ observations: [Observation]) {
        self.observations = observations
    }

    func observe() -> Observation {
        let observation = observations[min(index, observations.count - 1)]
        if index < observations.count - 1 {
            index += 1
        }
        return observation
    }
}

@MainActor
private final class RecordingExecutionDriver: AgentExecutionDriver {
    var intents: [ActionIntent] = []
    var decisions: [PlannerDecision] = []
    private let handler: (ActionIntent, PlannerDecision, ElementCandidate?) -> ToolResult

    init(handler: @escaping (ActionIntent, PlannerDecision, ElementCandidate?) -> ToolResult) {
        self.handler = handler
    }

    func execute(
        intent: ActionIntent,
        plannerDecision: PlannerDecision,
        selectedCandidate: ElementCandidate?
    ) -> ToolResult {
        intents.append(intent)
        decisions.append(plannerDecision)
        return handler(intent, plannerDecision, selectedCandidate)
    }
}
