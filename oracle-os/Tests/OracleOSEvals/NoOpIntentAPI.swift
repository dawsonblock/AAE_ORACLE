import Foundation
@testable import OracleOS

struct NoOpIntentAPI: IntentAPI {
    func submitIntent(_ intent: Intent) async throws -> IntentResponse {
        IntentResponse(
            intentID: intent.id,
            outcome: .skipped,
            summary: "No-op eval orchestrator",
            cycleID: UUID()
        )
    }

    func queryState() async throws -> RuntimeSnapshot {
        RuntimeSnapshot(summary: "No-op eval orchestrator")
    }
}