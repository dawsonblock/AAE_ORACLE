from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path

from fastapi import APIRouter, HTTPException

from aae.analysis.replay import ReplayEngine
from aae.analysis.structured_logger import StructuredEventLogger, generate_trace_id
from aae.oracle_bridge.contracts import ContractVersion, ExperimentResultRequest as CanonicalExperimentResultRequest, PlanRequest
from aae.oracle_bridge.oracle_adapters import (
    ExperimentResultResponse,
    OraclePlanRequest,
    OracleExperimentResultRequest,
    convert_oracle_request,
    convert_oracle_result_request,
)
from aae.oracle_bridge.result_service import ResultService, get_telemetry
from aae.oracle_bridge.service import OraclePlanningBridge
from aae.storage.experiment_store import ExperimentStore
from aae.storage.ranking_store import RankingStore

router = APIRouter(prefix="/api/oracle", tags=["oracle"])
BRIDGE = OraclePlanningBridge()
RESULT_SERVICE = ResultService()
_experiment_store = ExperimentStore(db="experiments.db")
_ranking_store = RankingStore(db="rankings.db")
_event_logger = StructuredEventLogger()
_replay_engine = ReplayEngine(experiment_store=_experiment_store, event_log_path=_event_logger.path)


def _read_recent_events(limit: int = 200) -> list[dict]:
    path = Path(_event_logger.path)
    if not path.exists():
        return []
    events: deque[dict] = deque(maxlen=limit)
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(events)


def _repair_usefulness(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _failure_mode(request: OracleExperimentResultRequest) -> str | None:
    if request.execution_status == "success":
        return None
    if request.safety_violations:
        return "safety_violation"
    if not request.build_results.success:
        return "build_error"
    if not request.test_results.is_success():
        return "test_failure"
    if request.execution_status == "partial":
        return "runtime_error"
    return "unknown"


def _fusion_stats_snapshot() -> dict:
    recent_events = _read_recent_events()
    recent_experiments = _experiment_store.list_recent(limit=50)
    goal_ids = {
        *(event.get("goal_id") for event in recent_events if event.get("goal_id")),
        *(event.get("goal") for event in recent_experiments if event.get("goal")),
    }
    result_events = [
        event for event in recent_events if event.get("stage") in {"result", "result_ingest"}
    ]
    accepted = sum(1 for item in recent_experiments if item.get("accepted"))
    total = len(recent_experiments)
    rejected = total - accepted
    test_rates = [
        float((event.get("metrics") or {}).get("test_pass_rate", 0.0))
        for event in result_events
        if isinstance(event.get("metrics"), dict)
    ]
    score_lifts = [float(event.get("score", 0.0)) for event in result_events]
    fallback_count = sum(1 for event in recent_events if event.get("stage") in {"fallback", "rejection"})
    source_breakdown = {"oracle_native": 0, "aae_advised": 0, "hybrid": 0}
    for event in recent_events:
        if event.get("stage") != "candidate":
            continue
        source = event.get("source", "aae_advised")
        source_breakdown[source] = source_breakdown.get(source, 0) + 1

    candidate_rankings = []
    for experiment in recent_experiments:
        candidate_rankings.append(
            {
                "goal_id": experiment["goal"],
                "candidate_id": experiment["candidate_id"],
                "predicted_score": experiment["score"],
                "accepted": experiment["accepted"],
                "created_at": experiment["created_at"],
            }
        )

    return {
        "incoming_goals": {
            "count": len(goal_ids),
            "active": len(goal_ids),
            "pending": 0,
        },
        "candidate_rankings": candidate_rankings,
        "acceptance_stats": {
            "accepted": accepted,
            "rejected": rejected,
            "total": total,
        },
        "test_pass_rate": sum(test_rates) / len(test_rates) if test_rates else 0.0,
        "average_score_lift": sum(score_lifts) / len(score_lifts) if score_lifts else 0.0,
        "fallback_frequency": fallback_count / (total or 1),
        "source_breakdown": source_breakdown,
        "ranking_snapshot": _ranking_store.get_all_scores(),
    }


@router.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok', 'engine': 'aae.oracle_bridge.v1'}


@router.post('/plan')
async def plan(request: OraclePlanRequest):
    # Validate contract version
    if request.version != ContractVersion.V1.value:
        raise HTTPException(status_code=400, detail=f"Unsupported contract version: {request.version}")

    # Generate trace_id if not provided
    trace_id = request.trace_id or generate_trace_id()
    if request.trace_id is None:
        # Propagate generated trace_id back onto the request for downstream logging/observability
        request.trace_id = trace_id
    canonical_request: PlanRequest = convert_oracle_request(request)

    start = time.perf_counter()
    response_model = BRIDGE.plan(request)
    duration_ms = (time.perf_counter() - start) * 1000

    for candidate in response_model.candidates:
        _event_logger.log(
            {
                "stage": "candidate",
                "goal_id": request.goal_id,
                "trace_id": trace_id,
                "candidate_id": candidate.candidate_id,
                "kind": candidate.kind,
                "confidence": candidate.confidence,
                "source": "aae_advised",
            }
        )

    _event_logger.log(
        {
            "stage": "plan",
            "goal_id": request.goal_id,
            "trace_id": trace_id,
            "candidate_count": len(response_model.candidates),
            "latency_ms": round(duration_ms, 2),
            "canonical_request": canonical_request.model_dump(mode="json"),
        }
    )

    response = response_model.model_dump()
    response["trace_id"] = trace_id
    return response


@router.post('/experiment_result')
async def receive_experiment_result(
    request: OracleExperimentResultRequest
) -> dict:
    """Receive experiment execution results and return scoring feedback."""
    trace_id = request.trace_id or generate_trace_id()
    if request.trace_id is None:
        request.trace_id = trace_id

    canonical_result: CanonicalExperimentResultRequest = convert_oracle_result_request(request)
    ingested = RESULT_SERVICE.ingest(canonical_result.model_dump(mode="json"))

    _event_logger.log_result(
        goal_id=request.goal_id,
        trace_id=trace_id,
        candidate_id=request.candidate_id,
        result=request.execution_status,
        score=ingested["score"],
        latency_ms=request.elapsed_time_seconds * 1000.0,
    )

    response = ExperimentResultResponse(
        score=ingested["score"],
        failure_mode=_failure_mode(request),
        repair_usefulness=_repair_usefulness(ingested["score"]),
        feedback_summary=f"Processed {request.candidate_id} with score {ingested['score']:.2f}",
        updated_candidate_ranking=ingested["updated_candidate_ranking"],
    )
    return response.model_dump()


@router.get('/fusion-stats')
async def get_fusion_stats():
    """Get Oracle-AAE fusion observability statistics (Phase 6)."""
    return _fusion_stats_snapshot()


@router.get('/stats')
async def get_stats():
    """Get rejection telemetry and system statistics."""
    telemetry = get_telemetry()
    return telemetry.get_stats()


@router.get('/experiments/replay/{goal_id}')
async def replay_goal(goal_id: str):
    """Replay full experiment history for a goal."""
    history = _replay_engine.get_goal_history(goal_id)
    return {"goal_id": goal_id, "experiments": history}


@router.get('/experiments/trace/{trace_id}')
async def replay_trace(trace_id: str):
    """Replay all events for a trace ID."""
    events = _replay_engine.get_history(trace_id)
    return {"trace_id": trace_id, "events": events}


@router.get('/experiments/recent')
async def recent_experiments(limit: int = 50):
    """Get most recent experiments."""
    experiments = _replay_engine.get_recent(limit=limit)
    return {"experiments": experiments}


@router.post('/record-acceptance')
async def record_acceptance(payload: dict):
    """Record candidate acceptance/rejection for observability."""
    _event_logger.log(
        {
            "stage": "acceptance",
            "accepted": bool(payload.get("accepted", False)),
            "source": payload.get("source", "unknown"),
            "trace_id": payload.get("trace_id"),
            "goal_id": payload.get("goal_id"),
        }
    )
    return {"status": "recorded"}


@router.post('/record-fallback')
async def record_fallback():
    """Record fallback to Oracle-native plan."""
    _event_logger.log({"stage": "fallback"})
    return {"status": "recorded"}
