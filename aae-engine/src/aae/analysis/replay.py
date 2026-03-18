"""Replay engine — reconstruct decisions, candidates, and outcomes from history.

Provides both SQLite-based replay from experiment_store and JSONL-based
replay from structured event logs.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from aae.storage.experiment_store import ExperimentStore


class ReplayEngine:
    """Replay experiment and event history for debugging and analysis."""

    def __init__(
        self,
        experiment_store: Optional[ExperimentStore] = None,
        event_log_path: Optional[str] = None,
    ):
        self.store = experiment_store or ExperimentStore()
        self.event_log_path = event_log_path

    def get_goal_history(self, goal: str) -> List[Dict[str, Any]]:
        """Retrieve full experiment history for a goal from SQLite."""
        return self.store.get_history(goal)

    def get_trace_events(self, trace_id: str) -> List[Dict[str, Any]]:
        """Retrieve all events sharing a trace ID from the JSONL log."""
        if not self.event_log_path or not os.path.exists(self.event_log_path):
            return self.store.get_by_trace(trace_id)

        events: List[Dict[str, Any]] = []
        with open(self.event_log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if record.get("trace_id") == trace_id:
                        events.append(record)
                except json.JSONDecodeError:
                    continue
        return events

    def get_candidate_history(self, candidate_id: str) -> List[Dict[str, Any]]:
        """Retrieve all experiments for a specific candidate."""
        return self.store.get_by_candidate(candidate_id)

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve most recent experiments."""
        return self.store.get_all(limit=limit)
