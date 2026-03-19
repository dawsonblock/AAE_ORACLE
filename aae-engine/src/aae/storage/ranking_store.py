from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional


class RankingStore:
    def __init__(self, db_path: str = "rankings.db", db: Optional[str] = None) -> None:
        self.conn = sqlite3.connect(db or db_path, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rankings (
                candidate_id TEXT PRIMARY KEY,
                score_total REAL NOT NULL,
                accept_count INTEGER NOT NULL,
                reject_count INTEGER NOT NULL,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def update(self, candidate_id: str, *args: Any) -> float:
        if len(args) == 2 and isinstance(args[0], str):
            goal_id = args[0]
            delta = float(args[1])
            accepted = delta >= 0
            storage_id = self._goal_scoped_id(candidate_id, goal_id)
        else:
            delta = float(args[0])
            accepted = bool(args[1])
            storage_id = candidate_id

        current = self.get(storage_id)
        score_total = current["score_total"] + delta
        accept_count = current["accept_count"] + (1 if accepted else 0)
        reject_count = current["reject_count"] + (0 if accepted else 1)

        self.conn.execute(
            """
            INSERT INTO rankings(candidate_id, score_total, accept_count, reject_count)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                score_total = excluded.score_total,
                accept_count = excluded.accept_count,
                reject_count = excluded.reject_count,
                last_updated = CURRENT_TIMESTAMP
            """,
            (storage_id, score_total, accept_count, reject_count),
        )
        self.conn.commit()
        return score_total

    def get(self, candidate_id: str) -> Dict[str, Any]:
        cur = self.conn.execute(
            """
            SELECT candidate_id, score_total, accept_count, reject_count, last_updated
            FROM rankings
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {
                "candidate_id": candidate_id,
                "score_total": 0.0,
                "accept_count": 0,
                "reject_count": 0,
                "last_updated": None,
            }
        return {
            "candidate_id": row[0],
            "score_total": row[1],
            "accept_count": row[2],
            "reject_count": row[3],
            "last_updated": row[4],
        }

    def get_score(self, candidate_id: str, goal_id: str) -> float:
        return self.get(self._goal_scoped_id(candidate_id, goal_id))["score_total"]

    def get_rankings(self, goal_id: str) -> List[Dict[str, Any]]:
        prefix = self._goal_scoped_id("", goal_id)
        cur = self.conn.execute(
            """
            SELECT candidate_id, score_total, accept_count, reject_count, last_updated
            FROM rankings
            WHERE candidate_id LIKE ?
            ORDER BY score_total DESC
            """,
            (f"{prefix}%",),
        )
        rows = []
        for row in cur.fetchall():
            record = self.get(row[0])
            record["candidate_id"] = row[0].split("::", 1)[1]
            rows.append(record)
        return rows

    def get_all_scores(self) -> Dict[str, Dict[str, float]]:
        cur = self.conn.execute("SELECT candidate_id, score_total FROM rankings")
        scores: Dict[str, Dict[str, float]] = {}
        for candidate_id, score_total in cur.fetchall():
            if "::" in candidate_id:
                goal_id, raw_candidate_id = candidate_id.split("::", 1)
            else:
                goal_id, raw_candidate_id = "", candidate_id
            scores.setdefault(goal_id, {})[raw_candidate_id] = score_total
        return scores

    def close(self) -> None:
        self.conn.close()

    def _goal_scoped_id(self, candidate_id: str, goal_id: str) -> str:
        return f"{goal_id}::{candidate_id}"
