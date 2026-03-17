import Foundation

/// DEPRECATED: Direct code execution bypass.
/// All code actions must route through VerifiedExecutor → ToolDispatcher.
/// This type will be removed once RuntimeExecutionDriver is fully converted to the IntentAPI path.
@MainActor
public struct CodeActionGateway {
    public let context: RuntimeContext
    
    public init(context: RuntimeContext) {
        self.context = context
    }
    
    public func execute(_ intent: ActionIntent) -> ToolResult {
        guard let command = intent.codeCommand else {
            return ToolResult(success: false, error: "Missing structured code command")
        }

        do {
            switch command.category {
            case .indexRepository:
                let snapshot = context.repositoryIndexer.indexIfNeeded(workspaceRoot: URL(fileURLWithPath: command.workspaceRoot, isDirectory: true))
                return ToolResult(
                    success: true,
                    data: [
                        "method": "repository-index",
                        "code_execution": [
                            "workspace_root": snapshot.workspaceRoot,
                            "repository_snapshot_id": snapshot.id,
                            "build_tool": snapshot.buildTool.rawValue,
                            "file_count": snapshot.files.count,
                        ],
                    ]
                )
            case .searchCode:
                let snapshot = context.repositoryIndexer.indexIfNeeded(workspaceRoot: URL(fileURLWithPath: command.workspaceRoot, isDirectory: true))
                let query = intent.text ?? intent.query ?? ""
                let matches = CodeSearch().search(query: query, in: snapshot)
                return ToolResult(
                    success: true,
                    data: [
                        "method": "repository-search",
                        "matches": matches.map { ["path": $0.path, "score": $0.score, "symbol_names": $0.symbolNames] },
                        "code_execution": [
                            "workspace_root": snapshot.workspaceRoot,
                            "repository_snapshot_id": snapshot.id,
                            "match_count": matches.count,
                        ],
                    ]
                )
            case .openFile:
                guard let relativePath = command.workspaceRelativePath else {
                    return ToolResult(success: false, error: "Missing file path")
                }
                let scope = try WorkspaceScope(rootURL: URL(fileURLWithPath: command.workspaceRoot, isDirectory: true))
                let fileURL = try scope.resolve(relativePath: relativePath)
                guard let fileURL,
                      let data = FileManager.default.contents(atPath: fileURL.path),
                      let text = String(data: data, encoding: .utf8)
                else {
                    return ToolResult(success: false, error: "Unable to read \(relativePath)")
                }
                return ToolResult(
                    success: true,
                    data: [
                        "method": "workspace-read",
                        "content": text,
                        "code_execution": [
                            "workspace_root": command.workspaceRoot,
                            "workspace_relative_path": relativePath,
                        ],
                    ]
                )
            case .editFile, .writeFile, .generatePatch:
                guard let relativePath = command.workspaceRelativePath else {
                    return ToolResult(success: false, error: "Missing file path")
                }
                let scope = try WorkspaceScope(rootURL: URL(fileURLWithPath: command.workspaceRoot, isDirectory: true))
                let fileURL = try scope.resolve(relativePath: relativePath)
                guard let fileURL else {
                    return ToolResult(success: false, error: "Unable to resolve \(relativePath)")
                }
                let existing = FileManager.default.contents(atPath: fileURL.path).flatMap { String(data: $0, encoding: .utf8) } ?? ""
                let content = intent.text ?? existing
                try content.write(to: fileURL, atomically: true, encoding: .utf8)
                return ToolResult(
                    success: true,
                    data: [
                        "method": "workspace-write",
                        "patch_id": UUID().uuidString,
                        "code_execution": [
                            "workspace_root": command.workspaceRoot,
                            "workspace_relative_path": relativePath,
                            "previous_length": existing.count,
                            "new_length": content.count,
                        ],
                    ]
                )
            case .parseBuildFailure, .parseTestFailure:
                let snapshot = context.repositoryIndexer.indexIfNeeded(workspaceRoot: URL(fileURLWithPath: command.workspaceRoot, isDirectory: true))
                let output = intent.text ?? ""
                let likelyRootCause = CodeQueryEngine().findLikelyRootCause(
                    failureDescription: output,
                    in: snapshot
                )
                let likelyFiles = likelyRootCause.map(\.path)
                return ToolResult(
                    success: !likelyFiles.isEmpty,
                    data: [
                        "method": "failure-parser",
                        "likely_files": likelyFiles,
                        "ranked_candidates": likelyRootCause.map { candidate in
                            [
                                "path": candidate.path,
                                "score": candidate.score,
                                "affected_tests": candidate.impact.affectedTests.map(\.path),
                                "build_targets": candidate.impact.buildTargets.map(\.name),
                            ]
                        },
                        "code_execution": [
                            "workspace_root": snapshot.workspaceRoot,
                            "repository_snapshot_id": snapshot.id,
                        ],
                    ],
                    error: likelyFiles.isEmpty ? "No relevant files found" : nil
                )
            case .build, .test, .formatter, .linter, .gitStatus, .gitBranch, .gitCommit, .gitPush:
                let commandResult = try context.workspaceRunner.execute(spec: command)
                let summary = summarize(commandResult.stderr.isEmpty ? commandResult.stdout : commandResult.stderr)
                var codeExecution: [String: Any] = [
                    "workspace_root": command.workspaceRoot,
                    "command_category": command.category.rawValue,
                    "summary": command.summary,
                    "stdout": commandResult.stdout,
                    "stderr": commandResult.stderr,
                    "exit_code": commandResult.exitCode,
                    "elapsed_ms": commandResult.elapsedMs,
                ]
                if command.category == .build {
                    codeExecution["build_result_summary"] = summary
                }
                if command.category == .test {
                    codeExecution["test_result_summary"] = summary
                }
                return ToolResult(
                    success: commandResult.succeeded,
                    data: [
                        "method": "workspace-runner",
                        "code_execution": codeExecution,
                    ],
                    error: commandResult.succeeded ? nil : summary
                )
            }
        } catch {
            return ToolResult(success: false, error: error.localizedDescription)
        }
    }

    private func summarize(_ output: String) -> String {
        let trimmed = output.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "No output" }
        return trimmed.split(separator: "\n").prefix(3).joined(separator: " ")
    }
}
