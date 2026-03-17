import AXorcist
import Foundation

public enum RecipeInducer {
    @MainActor
    public static func induce(
        name: String,
        trace: [TraceEvent],
        observation: Observation
    ) -> Recipe {
        let workflows = induceWorkflows(goalPattern: name, trace: trace)
        guard let workflow = workflows.first else {
            return Recipe(
                schemaVersion: 2,
                name: name,
                description: "Induced from trace",
                app: observation.app ?? "unknown",
                params: nil,
                preconditions: nil,
                steps: [],
                postconditions: nil,
                constraints: nil,
                onFailure: nil
            )
        }

        let steps = workflow.steps.enumerated().map { index, step in
            RecipeStep(
                id: index,
                action: step.actionContract.skillName,
                target: locator(for: step),
                params: workflow.parameterSlots.isEmpty ? nil : Dictionary(
                    uniqueKeysWithValues: workflow.parameterSlots.map { ($0, "") }
                ),
                waitAfter: nil,
                note: step.notes.isEmpty ? nil : step.notes.joined(separator: " | "),
                onFailure: nil
            )
        }

        let (parameterizedSteps, params) = ParameterExtractor.extract(steps: steps)
        let recipeParams = params.reduce(into: [String: RecipeParam]()) { result, param in
            result[param] = RecipeParam(
                type: "string",
                description: "workflow-extracted parameter",
                required: true
            )
        }

        return Recipe(
            schemaVersion: 2,
            name: name,
            description: "Induced from verified workflow",
            app: observation.app ?? "unknown",
            params: recipeParams.isEmpty ? nil : recipeParams,
            preconditions: nil,
            steps: parameterizedSteps,
            postconditions: nil,
            constraints: nil,
            onFailure: nil
        )
    }

    public static func induceWorkflows(
        goalPattern: String,
        trace: [TraceEvent]
    ) -> [WorkflowPlan] {
        WorkflowSynthesizer().synthesize(
            goalPattern: goalPattern,
            events: trace
        )
    }

    @MainActor
    private static func locator(for step: WorkflowStep) -> Locator? {
        if let domID = step.actionContract.targetLabel, step.actionContract.locatorStrategy == "dom-id" {
            return LocatorBuilder.build(domId: domID)
        }
        if let query = step.semanticQuery?.text ?? step.actionContract.targetLabel {
            return LocatorBuilder.build(query: query)
        }
        return nil
    }
}
