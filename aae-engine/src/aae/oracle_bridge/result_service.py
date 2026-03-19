from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Optional

from aae.analysis.experiment_evaluator import ExperimentEvaluator
from aae.analysis.replay import ReplayEngine
from aae.observability.event_logger import EventLogger
from aae.oracle_bridge.contracts import ExperimentResultRequest
from aae.storage.experiment_store import ExperimentStore
from aae.storage.ranking_store import RankingStore


class RejectionTelemetry:
    def __init__(self) -> None:
        self.accepted = 0
        self.rejected = 0
        self.rejection_reasons: Dict[str, int] = defaultdict(int)

    def record_acceptance(self) -> None:
        self.accepted += 1

    def record_rejection(self, reason: str) -> None:
        self.rejected += 1
        self.rejection_reasons[reason] += 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "accepted": self.accepted,
            "rejected": self.rejected,
            "total": self.accepted + self.rejected,
            "rejection_reasons": dict(self.rejection_reasons),
        }


_telemetry = RejectionTelemetry()


def get_telemetry() -> RejectionTelemetry:
    return _telemetry


class ResultService:
    def __init__(self) -> None:
        self.evaluator = ExperimentEvaluator()
        self.experiment_store = ExperimentStore()
        self.ranking_store = RankingStore()
        self.replay_engine = ReplayEngine()
        self.event_logger = EventLogger()

    def ingest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request = ExperimentResultRequest.model_validate(payload)
        evaluation_input = {
            "status": request.execution_result,
            "execution_result": request.execution_result,
            "accepted": request.accepted,
            **request.metrics,
        }
        evaluation = self.evaluator.evaluate(request.goal, evaluation_input)
        score = evaluation["score"]
        combined_metrics = {
            **request.metrics,
            **evaluation["metrics"],
        }

        before_rank = self._rank_position(request.goal, request.candidate_id)

        self.experiment_store.log(
            trace_id=request.trace_id,
            goal=request.goal,
            candidate_id=request.candidate_id,
            candidate_type=request.candidate_type.value,
            target_files=request.target_files,
            execution_result=request.execution_result,
            score=score,
            accepted=request.accepted,
        )

        delta = score if request.accepted else -max(0.1, 1.0 - score)
        self.ranking_store.update(request.candidate_id, request.goal, delta)
        after_rank = self._rank_position(request.goal, request.candidate_id)
        rank_change = self._rank_change(before_rank, after_rank)

        if request.accepted:
            _telemetry.record_acceptance()
        else:
            _telemetry.record_rejection("not_accepted")

        self.event_logger.log(
            {
                "event": "result_ingested",
                "stage": "result_ingest",
                "trace_id": request.trace_id,
                "goal": request.goal,
                "candidate_id": request.candidate_id,
                "accepted": request.accepted,
                "score": score,
                "metrics": combined_metrics,
            }
        )

        return {
            "trace_id": request.trace_id,
            "goal": request.goal,
            "candidate_id": request.candidate_id,
            "score": score,
            "accepted": request.accepted,
            "execution_result": request.execution_result,
            "metrics": combined_metrics,
            "updated_candidate_ranking": [
                {
                    "candidate_id": request.candidate_id,
                    "new_score": self.ranking_store.get_score(request.candidate_id, request.goal),
                    "rank_change": rank_change,
                }
            ],
        }

    def replay(self, trace_id: str):
        return self.replay_engine.get_history(trace_id)

    def _rank_position(self, goal: str, candidate_id: str) -> Optional[int]:
        rankings = self.ranking_store.get_rankings(goal)
        for index, record in enumerate(rankings, start=1):
            if record["candidate_id"] == candidate_id:
                return index
        return None

    @staticmethod
    def _rank_change(before_rank: Optional[int], after_rank: Optional[int]) -> int:
        if after_rank is None:
            return 0
        if before_rank is None:
            return 1
        return before_rank - after_rank


ExperimentResultService = ResultService

