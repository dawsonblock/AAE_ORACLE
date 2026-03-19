from typing import Any, Dict, List


class CandidateRanker:
    def __init__(self, ranking_store) -> None:
        self.ranking_store = ranking_store

    def _candidate_value(self, candidate: Dict[str, Any] | Any, key: str, default: Any) -> Any:
        if isinstance(candidate, dict):
            return candidate.get(key, default)
        return getattr(candidate, key, default)

    def _score(self, candidate: Dict[str, Any] | Any, goal_id: str | None = None) -> float:
        candidate_id = self._candidate_value(candidate, "id", None) or self._candidate_value(
            candidate, "candidate_id", ""
        )
        if goal_id and hasattr(self.ranking_store, "get_score"):
            prior = self.ranking_store.get_score(candidate_id, goal_id)
        else:
            record = self.ranking_store.get(candidate_id)
            prior = record.get("score_total", 0.0)
        confidence = self._candidate_value(candidate, "confidence", 0.0)
        coverage_gain = self._candidate_value(candidate, "coverage_gain", 0.0)
        risk = self._candidate_value(candidate, "risk", "")
        safety_bonus = 0.1 if risk == "low" else 0.0

        return (confidence * 0.6) + (prior * 0.25) + (coverage_gain * 0.05) + safety_bonus

    def rank(self, candidates: List[Dict[str, Any]] | List[Any], goal_id: str | None = None) -> List[Any]:
        return sorted(candidates, key=lambda candidate: self._score(candidate, goal_id=goal_id), reverse=True)
