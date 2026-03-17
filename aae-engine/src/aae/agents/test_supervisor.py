from .supervisor import SupervisorAgent

class TestSupervisor(SupervisorAgent):
    def __init__(self, supervisor_id, queue, event_bus, spawn_controller):
        super().__init__(supervisor_id, "test", queue, event_bus)
        self.spawn_controller = spawn_controller

    def decompose(self, task):
        return []

    def review(self, worker_results):
        return worker_results
