import uuid
from .supervisor import SupervisorAgent

class RepairSupervisor(SupervisorAgent):
    def __init__(self, supervisor_id, queue, event_bus, spawn_controller):
        super().__init__(supervisor_id, "repair", queue, event_bus)
        self.spawn_controller = spawn_controller

    def decompose(self, task):
        subtasks = []
        for candidate in task.get("candidates", [])[:5]:
            if not self.spawn_controller.can_spawn_worker(self.supervisor_id):
                break
            worker_id = f"worker-{uuid.uuid4()}"
            self.spawn_controller.register_worker(
                self.supervisor_id, 
                worker_id, 
                "candidate_repair"
            )
            subtasks.append({
                "worker_id": worker_id,
                "command": candidate["command"],
                "candidate": candidate,
            })
        return subtasks

    def review(self, worker_results):
        successful = [r for r in worker_results if r.get("verified")]
        return successful[:1]
