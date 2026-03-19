import copy

from aae.contracts.workflow import EventEnvelope


class WorldState:
    def __init__(self):
        self._state = {
            "last_execution": None,
            "last_evaluation": None,
            "agent_tree": {},
        }

    def apply(self, event: EventEnvelope) -> None:
        if isinstance(event, dict):
            event_type = event.get("event_type", "") or event.get("type", "")
            payload = event.get("payload", {})
            if isinstance(payload, dict):
                payload = {
                    "agent_id": event.get("agent_id"),
                    "parent_agent_id": event.get("parent_agent_id"),
                    **payload,
                }
        else:
            event_type = event.event_type
            payload = event.payload

        if event_type == "execution_completed":
            self._state["last_execution"] = payload
        elif event_type == "evaluation_completed":
            self._state["last_evaluation"] = payload
        elif event_type in {"supervisor_spawned", "worker_spawned"}:
            agent_id = payload.get("agent_id", "unknown")
            self._state["agent_tree"][agent_id] = {
                "parent_agent_id": payload.get("parent_agent_id"),
                "payload": payload,
            }

    def snapshot(self):
        return copy.deepcopy(self._state)
