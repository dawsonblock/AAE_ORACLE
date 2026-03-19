from fastapi import APIRouter

from aae.analysis.replay import ReplayEngine
from aae.storage.experiment_store import ExperimentStore
from aae.storage.ranking_store import RankingStore

router = APIRouter(prefix="/api/system", tags=["system"])
experiments = ExperimentStore()
rankings = RankingStore()
replay = ReplayEngine()


@router.get("/experiments")
def list_experiments():
    return experiments.list_recent()


@router.get("/experiments/{trace_id}")
def experiment_by_trace(trace_id: str):
    return replay.get_history(trace_id)


@router.get("/rankings/{candidate_id}")
def ranking(candidate_id: str):
    return rankings.get(candidate_id)
