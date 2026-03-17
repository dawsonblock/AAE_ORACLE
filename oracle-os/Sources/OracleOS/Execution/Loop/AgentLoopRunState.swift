import Foundation

struct AgentLoopRunState {
    var latestWorldState: WorldState?
    var lastAction: ActionIntent?
    var diagnostics = LoopDiagnostics.empty
    var budgetState = LoopBudgetState()
    var recentFailureCount: Int = 0
}
