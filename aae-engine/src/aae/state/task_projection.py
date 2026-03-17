class TaskStateProjection:
    def apply_all(self, events):
        state = {}
        for e in events:
            task_id = e["task_id"]
            state.setdefault(task_id, {"events": [], "status": "unknown"})
            state[task_id]["events"].append(e)
            if e["type"] == "task_started":
                state[task_id]["status"] = "running"
            elif e["type"] == "evaluation_completed":
                state[task_id]["status"] = "evaluated"
        return state
