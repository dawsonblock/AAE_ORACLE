"""Deterministic candidate ranker.

Combines real-time confidence with historical ranking priors to produce
a stable, reproducible ordering of candidates.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from aae.storage.ranking_store import RankingStore


class CandidateRanker:
    """Rank candidates using confidence and historical score priors."""

    def __init__(self, ranking_store: "RankingStore"):
        self.ranking_store = ranking_store

    def rank(self, candidates: list, goal_id: str = "") -> list:
        """Sort candidates by blended score (confidence × 0.7 + prior × 0.3).

        Parameters
        ----------
        candidates : list
            Candidate objects with `candidate_id` and `confidence` attributes.
        goal_id : str
            Goal context for prior score lookup.

        Returns
        -------
        list
            Candidates sorted best-first.
        """

        def _score(c) -> float:
            cid = getattr(c, "candidate_id", getattr(c, "id", ""))
            prior = self.ranking_store.get_score(cid, goal_id)
            confidence = getattr(c, "confidence", 0.0)
            return (confidence * 0.7) + (prior * 0.3)

        return sorted(candidates, key=_score, reverse=True)
