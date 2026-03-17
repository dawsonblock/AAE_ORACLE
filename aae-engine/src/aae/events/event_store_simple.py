from typing import List, Dict, Any
from .schema import Event


class EventStore:
    def __init__(self):
        self._events: List[Dict[str, Any]] = []

    def append(self, event_type: str, task_id: str, repo_id: str, agent_id: str, payload: Dict[str, Any], parent_agent_id=None):
        event = Event(
            type=event_type,
            task_id=task_id,
            repo_id=repo_id,
            agent_id=agent_id,
            parent_agent_id=parent_agent_id,
            payload=payload,
        )
        record = event.__dict__
        self._events.append(record)
        return record

    def all(self):
        return list(self._events)

    def by_task(self, task_id: str):
        return [e for e in self._events if e["task_id"] == task_id]

    def by_repo(self, repo_id: str):
        return [e for e in self._events if e["repo_id"] == repo_id]
