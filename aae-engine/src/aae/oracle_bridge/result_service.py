from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from aae.analysis.experiment_evaluator import ExperimentEvaluator
from aae.analysis.replay import ReplayEngine
from aae.observability.event_logger import EventLogger
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


@dataclass
class ProcessExperimentResult:
    score: float
    failure_mode: Optional[str]
    repair_usefulness: str
    feedback_summary: str
    updated_candidate_ranking: list[dict[str, Any]]

    def model_dump(self) -> Dict[str, Any]:
        return asdict(self)


class ResultService:
    def __init__(self) -> None:
        self.evaluator = ExperimentEvaluator()
        self.experiment_store = ExperimentStore()
        self.ranking_store = RankingStore()
        self.replay_engine = ReplayEngine()
        self.event_logger = EventLogger()

    def ingest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        trace_id = payload.get("trace_id")
        candidate_id = payload.get("candidate_id")
        goal = payload.get("goal")
        candidate_type = payload.get("candidate_type")
        target_files = payload.get("target_files", [])
        execution_result = payload.get("execution_result")
        accepted = bool(payload.get("accepted", False))

        if not trace_id:
            raise ValueError("missing trace_id")
        if not candidate_id:
            raise ValueError("missing candidate_id")
        if not execution_result:
            raise ValueError("missing execution_result")

        evaluation = self.evaluator.evaluate(goal, payload)
        score = evaluation["score"]

        self.experiment_store.log(
            trace_id=trace_id,
            goal=goal,
            candidate_id=candidate_id,
            candidate_type=candidate_type,
            target_files=target_files,
            execution_result=execution_result,
            score=score,
            accepted=accepted,
        )

        delta = score if accepted else -0.5
        self.ranking_store.update(candidate_id, delta, accepted)

        if accepted:
            _telemetry.record_acceptance()
        else:
            _telemetry.record_rejection("not_accepted")

        self.event_logger.log(
            {
                "stage": "result_ingest",
                "trace_id": trace_id,
                "goal": goal,
                "candidate_id": candidate_id,
                "accepted": accepted,
                "score": score,
            }
        )

        return {
            "trace_id": trace_id,
            "candidate_id": candidate_id,
            "score": score,
            "metrics": evaluation["metrics"],
        }

    def replay(self, trace_id: str):
        return self.replay_engine.get_history(trace_id)

    def process_experiment_result(self, request: Any) -> ProcessExperimentResult:
        execution_result = getattr(request, "execution_status", None) or getattr(
            request,
            "execution_result",
            "failure",
        )
        payload = {
            "trace_id": getattr(request, "trace_id", "legacy-trace"),
            "goal": getattr(request, "goal_id", None) or getattr(request, "goal", "repair"),
            "candidate_id": getattr(request, "candidate_id", ""),
            "candidate_type": getattr(request, "candidate_type", "patch"),
            "target_files": getattr(request, "touched_files", None)
            or getattr(request, "target_files", []),
            "accepted": execution_result == "success",
            "execution_result": execution_result,
            "metrics": {},
        }
        ingested = self.ingest(payload)
        return ProcessExperimentResult(
            score=ingested["score"],
            failure_mode=None if execution_result == "success" else "execution_failure",
            repair_usefulness="high" if ingested["score"] >= 0.8 else "medium",
            feedback_summary=f"Processed {payload['candidate_id']} with score {ingested['score']:.2f}",
            updated_candidate_ranking=[{"candidate_id": payload["candidate_id"], "new_score": ingested["score"]}],
        )


ExperimentResultService = ResultService

