from __future__ import annotations

import json
import os
from datetime import datetime, timezone

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
        experiments = [
            {
                "stage": "result",
                "source": "experiment_store",
                **record,
            }
            for record in self.store.get_by_trace(trace_id)
        ]
        events = self.get_trace_events(trace_id)
        merged = [*events, *experiments]
        return sorted(merged, key=self._sort_key)

    def get_goal_history(self, goal: str):
        return self.store.get_history(goal)

    def get_trace_events(self, trace_id: str):
        if not self.event_log_path or not os.path.exists(self.event_log_path):
            return []

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
        return sorted(events, key=self._sort_key)

    def get_recent(self, limit: int = 50):
        return self.store.list_recent(limit=limit)

    def _sort_key(self, record: dict) -> tuple[float, str]:
        timestamp = record.get("timestamp")
        if isinstance(timestamp, (int, float)):
            return (float(timestamp), str(record.get("stage", "")))

        created_at = record.get("created_at")
        if isinstance(created_at, str):
            try:
                parsed = datetime.fromisoformat(created_at.replace(" ", "T")).replace(tzinfo=timezone.utc)
                return (parsed.timestamp(), str(record.get("stage", "")))
            except ValueError:
                pass

        return (0.0, str(record.get("stage", "")))
