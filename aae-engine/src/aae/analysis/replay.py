from aae.storage.experiment_store import ExperimentStore


class ReplayEngine:
    def __init__(self, experiment_store: ExperimentStore | None = None) -> None:
        self.store = experiment_store or ExperimentStore()

    def get_history(self, trace_id: str):
        return self.store.get_by_trace(trace_id)

    def get_goal_history(self, goal: str):
        return self.store.get_history(goal)

    def get_recent(self, limit: int = 50):
        return self.store.list_recent(limit=limit)
