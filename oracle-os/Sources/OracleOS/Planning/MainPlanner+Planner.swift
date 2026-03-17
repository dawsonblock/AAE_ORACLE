import Foundation

// MARK: - MainPlanner + Planner conformance
// Makes MainPlanner available as the `Planner` implementation in RuntimeOrchestrator.

extension MainPlanner: Planner {
    /// Route-only façade: dispatch to the appropriate domain planner based on intent domain.
    /// INVARIANT: planners return Commands only — no execution, no state writes.
    public func plan(intent: Intent, context: PlannerContext) async throws -> any Command {
        switch intent.domain {
        case .ui:
            return try await planUIIntent(intent, context: context)
        case .code:
            return try await planCodeIntent(intent, context: context)
        case .system, .mixed:
            return try await planSystemIntent(intent, context: context)
        }
    }

    // MARK: - Domain Planners

    private func planUIIntent(_ intent: Intent, context: PlannerContext) async throws -> any Command {
        // Route UI intents to click/type/focus/read based on objective
        let objective = intent.objective.lowercased()
        let metadata = CommandMetadata(intentID: intent.id, planningStrategy: "ui", rationale: intent.objective)

        if objective.contains("click") || objective.contains("tap") || objective.contains("press") {
            let targetID = intent.metadata["targetID"] ?? intent.objective
            let app = intent.metadata["app"] ?? context.state.snapshot.activeApplication ?? "unknown"
            return ClickElementCommand(metadata: metadata, targetID: targetID, applicationBundleID: app)
        }

        if objective.contains("type") || objective.contains("enter") || objective.contains("input") {
            let text = intent.metadata["text"] ?? intent.objective
            let targetID = intent.metadata["targetID"] ?? "focused"
            return TypeTextCommand(metadata: metadata, targetID: targetID, text: text)
        }

        if objective.contains("focus") || objective.contains("switch") || objective.contains("activate") {
            let app = intent.metadata["app"] ?? context.state.snapshot.activeApplication ?? "unknown"
            return FocusWindowCommand(metadata: metadata, applicationBundleID: app)
        }

        if objective.contains("read") || objective.contains("get") || objective.contains("observe") {
            let targetID = intent.metadata["targetID"] ?? intent.objective
            return ReadElementCommand(metadata: metadata, targetID: targetID)
        }

        // Default: try to focus the active app
        let app = context.state.snapshot.activeApplication ?? "unknown"
        return FocusWindowCommand(metadata: metadata, applicationBundleID: app)
    }

    private func planCodeIntent(_ intent: Intent, context: PlannerContext) async throws -> any Command {
        let objective = intent.objective.lowercased()
        let metadata = CommandMetadata(intentID: intent.id, planningStrategy: "code", rationale: intent.objective)

        if objective.contains("search") || objective.contains("find") || objective.contains("query") {
            return SearchRepositoryCommand(metadata: metadata, query: intent.objective)
        }

        if objective.contains("read") || objective.contains("open") || objective.contains("view") {
            let path = intent.metadata["filePath"] ?? intent.objective
            return ReadFileCommand(metadata: metadata, filePath: path)
        }

        if objective.contains("edit") || objective.contains("modify") || objective.contains("patch") {
            let path = intent.metadata["filePath"] ?? ""
            let patch = intent.metadata["patch"] ?? intent.objective
            return ModifyFileCommand(metadata: metadata, filePath: path, patch: patch)
        }

        if objective.contains("build") || objective.contains("compile") {
            let workspacePath = intent.metadata["workspacePath"] ?? context.repositorySnapshot?.workspaceRoot ?? ""
            return RunBuildCommand(metadata: metadata, workspacePath: workspacePath)
        }

        if objective.contains("test") || objective.contains("run test") {
            return RunTestsCommand(metadata: metadata, filter: intent.metadata["filter"])
        }

        return SearchRepositoryCommand(metadata: metadata, query: intent.objective)
    }

    private func planSystemIntent(_ intent: Intent, context: PlannerContext) async throws -> any Command {
        let objective = intent.objective.lowercased()
        let metadata = CommandMetadata(intentID: intent.id, planningStrategy: "system", rationale: intent.objective)

        if objective.contains("launch") || objective.contains("open app") || objective.contains("start") {
            let bundleID = intent.metadata["bundleID"] ?? intent.objective
            return LaunchAppCommand(metadata: metadata, bundleID: bundleID)
        }

        if objective.contains("url") || objective.contains("http") || objective.contains("website") {
            let urlString = intent.metadata["url"] ?? intent.objective
            let url = URL(string: urlString) ?? URL(string: "about:blank")!
            return OpenURLCommand(metadata: metadata, url: url)
        }

        // Default: try to launch app
        let bundleID = intent.metadata["bundleID"] ?? intent.objective
        return LaunchAppCommand(metadata: metadata, bundleID: bundleID)
    }
}
