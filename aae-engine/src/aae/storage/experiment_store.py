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
        # Store only the database path and use per-operation connections to
        # avoid sharing a single connection across threads.
        self._db_path = db
        # For in-memory databases a single shared connection is required because
        # each call to sqlite3.connect(":memory:") creates a completely separate,
        # empty database. File-based databases continue to use per-operation
        # connections for thread safety.
        self._mem_conn: sqlite3.Connection | None = (
            self._make_connection() if db == ":memory:" else None
        )
        self._create_tables()

    def _make_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=3000")
        return conn

    def _connect(self) -> sqlite3.Connection:
        """Return a SQLite connection for a single operation.

        For in-memory databases the same connection is reused so that tables
        created during ``_create_tables`` remain visible to later operations.
        """
        if self._mem_conn is not None:
            return self._mem_conn
        return self._make_connection()

    def _create_tables(self) -> None:
        conn = self._connect()
        conn.execute(
            """
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
    """
        )
        conn.commit()
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
        conn = self._connect()
        conn.execute(
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
        conn.commit()
        return experiment_id

    def get_history(self, goal: str) -> List[Dict[str, Any]]:
        """Retrieve full experiment history for a goal."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM experiments WHERE goal = ? ORDER BY timestamp ASC",
            (goal,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_by_candidate(self, candidate_id: str) -> List[Dict[str, Any]]:
        """Retrieve experiments for a specific candidate."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM experiments WHERE candidate_id = ? ORDER BY timestamp ASC",
            (candidate_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_by_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Retrieve all experiments sharing a trace ID."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM experiments WHERE trace_id = ? ORDER BY timestamp ASC",
            (trace_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve most recent experiments."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT * FROM experiments ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the shared in-memory connection if one exists."""
        if self._mem_conn is not None:
            self._mem_conn.close()
            self._mem_conn = None
