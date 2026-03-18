"""Structured event logger — writes JSONL for full-system observability.

Every plan generation, candidate selection, and experiment result is
recorded as a structured line so traces can be replayed and audited.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, Optional


def _default_log_path() -> str:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(root, "logs", "events.jsonl")


class StructuredEventLogger:
    """Append-only JSONL event logger for system-wide observability."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or _default_log_path()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def log(self, event: Dict[str, Any]) -> None:
        """Append a structured event to the log file."""
        record = {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **event,
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def log_plan(
        self,
        goal_id: str,
        trace_id: str,
        candidate_count: int,
        latency_ms: float,
    ) -> None:
        self.log({
            "stage": "plan",
            "goal_id": goal_id,
            "trace_id": trace_id,
            "candidate_count": candidate_count,
            "latency_ms": round(latency_ms, 2),
        })

    def log_candidate(
        self,
        goal_id: str,
        trace_id: str,
        candidate_id: str,
        kind: str,
        confidence: float,
    ) -> None:
        self.log({
            "stage": "candidate",
            "goal_id": goal_id,
            "trace_id": trace_id,
            "candidate_id": candidate_id,
            "kind": kind,
            "confidence": confidence,
        })

    def log_result(
        self,
        goal_id: str,
        trace_id: str,
        candidate_id: str,
        result: str,
        score: float,
        latency_ms: float = 0.0,
    ) -> None:
        self.log({
            "stage": "result",
            "goal_id": goal_id,
            "trace_id": trace_id,
            "candidate_id": candidate_id,
            "result": result,
            "score": score,
            "latency_ms": round(latency_ms, 2),
        })

    def log_rejection(
        self,
        goal_id: str,
        trace_id: str,
        reason: str,
    ) -> None:
        self.log({
            "stage": "rejection",
            "goal_id": goal_id,
            "trace_id": trace_id,
            "reason": reason,
        })


def generate_trace_id() -> str:
    """Generate a unique trace ID for a goal execution."""
    return str(uuid.uuid4())
