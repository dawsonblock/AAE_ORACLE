from __future__ import annotations

from fastapi import APIRouter

from aae.storage.experiment_store import ExperimentStore
from aae.analysis.replay import ReplayEngine

router = APIRouter(prefix='/api/system', tags=['system'])

# Factory for file-backed SQLite experiment store to avoid sharing a single
# SQLite connection across concurrent FastAPI requests.
def get_experiment_store() -> ExperimentStore:
    return ExperimentStore(db="experiments.db")


@router.get('/experiments')
async def list_experiments(limit: int = 100):
    """List all experiments for the dashboard."""
    store = get_experiment_store()
    return store.get_all(limit=limit)


@router.get('/experiments/{goal_id}')
async def get_goal_experiments(goal_id: str):
    """Get experiments for a specific goal."""
    store = get_experiment_store()
    return store.get_history(goal_id)


@router.get('/replay/{goal_id}')
async def replay_goal(goal_id: str):
    """Full replay of a goal's history."""
    store = get_experiment_store()
    replay = ReplayEngine(experiment_store=store)
    return replay.get_goal_history(goal_id)
