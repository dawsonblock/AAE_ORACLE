class WorkerAgent:
    def __init__(self, worker_id, role, executor):
        """Worker leaf node for specific task execution (no spawning)."""
        self.worker_id = worker_id
        self.role = role
        self.executor = executor

    def run(self, subtask):
        """Executes patch attempts or regression tests via the executor."""
        return self.executor.execute(subtask.get("command", {}))
