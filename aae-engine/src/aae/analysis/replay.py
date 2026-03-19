from __future__ import annotations

import json
import os

from aae.storage.experiment_store import ExperimentStore


class ReplayEngine:
    def __init__(
        self,
        experiment_store: ExperimentStore | None = None,
        event_log_path: str | None = None,
    ) -> None:
        self.store = experiment_store or ExperimentStore()
        self.event_log_path = event_log_path

    def get_history(self, trace_id: str):
        return self.store.get_by_trace(trace_id)

    def get_goal_history(self, goal: str):
        return self.store.get_history(goal)

    def get_trace_events(self, trace_id: str):
        if not self.event_log_path or not os.path.exists(self.event_log_path):
            return self.store.get_by_trace(trace_id)

        events = []
        with open(self.event_log_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("trace_id") == trace_id:
                    events.append(record)
        return events

    def get_recent(self, limit: int = 50):
        return self.store.list_recent(limit=limit)
