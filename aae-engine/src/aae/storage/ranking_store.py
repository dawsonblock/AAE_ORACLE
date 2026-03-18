"""Persistent ranking store backed by SQLite.

Tracks candidate ranking scores that survive service restarts.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional


class RankingStore:
    """SQLite-backed ranking store for persistent candidate scoring."""

    def __init__(self, db: str = "experiments.db"):
        self.conn = sqlite3.connect(db, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS rankings (
            candidate_id TEXT NOT NULL,
            goal_id TEXT NOT NULL,
            score REAL NOT NULL DEFAULT 0.0,
            updates INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (candidate_id, goal_id)
        )
        """)
        self.conn.commit()

    def update(self, candidate_id: str, goal_id: str, delta: float) -> float:
        """Update a candidate's score by delta. Returns new score."""
        row = self.conn.execute(
            "SELECT score, updates FROM rankings WHERE candidate_id = ? AND goal_id = ?",
            (candidate_id, goal_id),
        ).fetchone()

        if row:
            new_score = row["score"] + delta
            new_updates = row["updates"] + 1
            self.conn.execute(
                "UPDATE rankings SET score = ?, updates = ? WHERE candidate_id = ? AND goal_id = ?",
                (new_score, new_updates, candidate_id, goal_id),
            )
        else:
            new_score = delta
            self.conn.execute(
                "INSERT INTO rankings (candidate_id, goal_id, score, updates) VALUES (?, ?, ?, 1)",
                (candidate_id, goal_id, new_score),
            )

        self.conn.commit()
        return new_score

    def get_score(self, candidate_id: str, goal_id: str) -> float:
        """Get the current score for a candidate."""
        row = self.conn.execute(
            "SELECT score FROM rankings WHERE candidate_id = ? AND goal_id = ?",
            (candidate_id, goal_id),
        ).fetchone()
        return row["score"] if row else 0.0

    def get_rankings(self, goal_id: str) -> List[Dict]:
        """Get ranked candidates for a goal, sorted by score descending."""
        cursor = self.conn.execute(
            "SELECT candidate_id, score, updates FROM rankings WHERE goal_id = ? ORDER BY score DESC",
            (goal_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_all_scores(self) -> Dict[str, Dict[str, float]]:
        """Get all candidate scores grouped by goal_id (goal_id -> {candidate_id -> score})."""
        cursor = self.conn.execute("SELECT goal_id, candidate_id, score FROM rankings")
        scores: Dict[str, Dict[str, float]] = {}
        for row in cursor.fetchall():
            goal_id = row["goal_id"]
            candidate_id = row["candidate_id"]
            score = row["score"]
            if goal_id not in scores:
                scores[goal_id] = {}
            scores[goal_id][candidate_id] = score
        return scores

    def close(self) -> None:
        self.conn.close()
