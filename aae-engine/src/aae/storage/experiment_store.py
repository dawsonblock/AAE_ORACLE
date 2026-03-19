from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any, Dict, List, Optional


class ExperimentStore:
    def __init__(self, db_path: str = "experiments.db", db: Optional[str] = None) -> None:
        self.conn = sqlite3.connect(db or db_path, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                trace_id TEXT,
                goal TEXT,
                candidate_id TEXT,
                candidate_type TEXT,
                target_files TEXT,
                execution_result TEXT,
                score REAL,
                accepted INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def log(
        self,
        trace_id: Optional[str] = None,
        goal: str = "",
        candidate_id: str = "",
        candidate_type: str = "patch",
        target_files: Optional[List[str]] = None,
        execution_result: Optional[str] = None,
        score: float = 0.0,
        accepted: bool = False,
        result: Optional[str] = None,
        failure_mode: Optional[str] = None,
        repair_usefulness: Optional[str] = None,
    ) -> str:
        experiment_id = str(uuid.uuid4())
        self.conn.execute(
            """
            INSERT INTO experiments (
                experiment_id, trace_id, goal, candidate_id, candidate_type,
                target_files, execution_result, score, accepted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                trace_id,
                goal,
                candidate_id,
                candidate_type,
                json.dumps(target_files or []),
                execution_result or result or "",
                score,
                1 if accepted else 0,
            ),
        )
        self.conn.commit()
        return experiment_id

    def get_by_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT experiment_id, trace_id, goal, candidate_id, candidate_type,
                   target_files, execution_result, score, accepted, created_at
            FROM experiments
            WHERE trace_id = ?
            ORDER BY created_at ASC
            """,
            (trace_id,),
        )
        rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT experiment_id, trace_id, goal, candidate_id, candidate_type,
                   target_files, execution_result, score, accepted, created_at
            FROM experiments
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_history(self, goal: str) -> List[Dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT experiment_id, trace_id, goal, candidate_id, candidate_type,
                   target_files, execution_result, score, accepted, created_at
            FROM experiments
            WHERE goal = ?
            ORDER BY created_at ASC
            """,
            (goal,),
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def get_by_candidate(self, candidate_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT experiment_id, trace_id, goal, candidate_id, candidate_type,
                   target_files, execution_result, score, accepted, created_at
            FROM experiments
            WHERE candidate_id = ?
            ORDER BY created_at ASC
            """,
            (candidate_id,),
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.list_recent(limit=limit)

    def close(self) -> None:
        self.conn.close()

    def _row_to_dict(self, row: tuple[Any, ...]) -> Dict[str, Any]:
        return {
            "experiment_id": row[0],
            "trace_id": row[1],
            "goal": row[2],
            "candidate_id": row[3],
            "candidate_type": row[4],
            "target_files": json.loads(row[5] or "[]"),
            "execution_result": row[6],
            "result": row[6],
            "score": row[7],
            "accepted": bool(row[8]),
            "created_at": row[9],
        }
