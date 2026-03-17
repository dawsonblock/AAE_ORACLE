import Foundation

public final class RunTestsSkill: CodeSkill {
    public let name = "run_tests"

    public init() {}

    public func resolve(
        taskContext: TaskContext,
        state: WorldState,
        memoryStore _: UnifiedMemoryStore
    ) throws -> SkillResolution {
        let workspaceRoot = try CodeSkillSupport.workspaceRoot(taskContext: taskContext, state: state)
        let snapshot = try CodeSkillSupport.repositorySnapshot(state: state, workspaceRoot: workspaceRoot)
        
        // Phase 3: Prioritize AAE recommended test command if available
        let command: String
        if let aaeTestCommand = taskContext.recommendedTestCommand, !aaeTestCommand.isEmpty {
            command = aaeTestCommand
        } else if let detectedCommand = BuildToolDetector.defaultTestCommand(for: snapshot.buildTool, workspaceRoot: workspaceRoot) {
            command = detectedCommand
        } else {
            throw CodeSkillResolutionError.noRelevantFiles("No test command available")
        }
        
        return SkillResolution(
            intent: .code(name: "Run tests", command: command),
            repositorySnapshotID: snapshot.id
        )
    }
}
