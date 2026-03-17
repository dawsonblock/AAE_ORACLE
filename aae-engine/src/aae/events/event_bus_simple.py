class EventBus:
    def __init__(self, store):
        self.store = store

    def publish(self, event_type, task_id, repo_id, agent_id, payload, parent_agent_id=None):
        return self.store.append(
            event_type=event_type,
            task_id=task_id,
            repo_id=repo_id,
            agent_id=agent_id,
            payload=payload,
            parent_agent_id=parent_agent_id,
        )
