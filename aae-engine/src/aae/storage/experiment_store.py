"""Persistent experiment store backed by SQLite.

Stores every experiment execution for replay, debugging, and learning
across service restarts.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ExperimentStore:
    """SQLite-backed experiment store for persistent learning history."""

    def __init__(self, db: str = "experiments.db"):
        self.conn = sqlite3.connect(db, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            goal TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            result TEXT NOT NULL,
            score REAL NOT NULL,
            failure_mode TEXT,
            repair_usefulness TEXT,
            trace_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.conn.commit()

    def log(
        self,
        goal: str,
        candidate_id: str,
        result: str,
        score: float,
        failure_mode: Optional[str] = None,
        repair_usefulness: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Log an experiment result. Returns the experiment ID."""
        experiment_id = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO experiments
               (id, goal, candidate_id, result, score, failure_mode,
                repair_usefulness, trace_id, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                experiment_id,
                goal,
                candidate_id,
                result,
                score,
                failure_mode,
                repair_usefulness,
                trace_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()
        return experiment_id

    def get_history(self, goal: str) -> List[Dict[str, Any]]:
        """Retrieve full experiment history for a goal."""
        cursor = self.conn.execute(
            "SELECT * FROM experiments WHERE goal = ? ORDER BY timestamp ASC",
            (goal,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_by_candidate(self, candidate_id: str) -> List[Dict[str, Any]]:
        """Retrieve experiments for a specific candidate."""
        cursor = self.conn.execute(
            "SELECT * FROM experiments WHERE candidate_id = ? ORDER BY timestamp ASC",
            (candidate_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_by_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Retrieve all experiments sharing a trace ID."""
        cursor = self.conn.execute(
            "SELECT * FROM experiments WHERE trace_id = ? ORDER BY timestamp ASC",
            (trace_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve most recent experiments."""
        cursor = self.conn.execute(
            "SELECT * FROM experiments ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()
