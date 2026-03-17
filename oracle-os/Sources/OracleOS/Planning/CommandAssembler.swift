import Foundation
/// Assembles a final Command from a domain planner decision.
public struct CommandAssembler {
    public init() {}
    public func assemble(intent: Intent, domain: IntentDomain, context: PlanningContext) throws -> any Command {
        let meta = CommandMetadata(intentID: intent.id, planningStrategy: domain.rawValue, rationale: intent.objective)
        switch domain {
        case .ui:    return ClickElementCommand(metadata: meta, targetID: "unknown", applicationBundleID: "")
        case .code:  return SearchRepositoryCommand(metadata: meta, query: intent.objective)
        case .system: return LaunchAppCommand(metadata: meta, bundleID: "")
        case .mixed:  return SearchRepositoryCommand(metadata: meta, query: intent.objective)
        }
    }
}
