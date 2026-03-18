from __future__ import annotations

from fastapi import APIRouter

from aae.storage.experiment_store import ExperimentStore
from aae.analysis.replay import ReplayEngine

router = APIRouter(prefix='/api/system', tags=['system'])

# In-memory SQLite for portability
_store = ExperimentStore(db=":memory:")
_replay = ReplayEngine(experiment_store=_store)


@router.get('/experiments')
async def list_experiments(limit: int = 100):
    """List all experiments for the dashboard."""
    return _store.get_all(limit=limit)


@router.get('/experiments/{goal_id}')
async def get_goal_experiments(goal_id: str):
    """Get experiments for a specific goal."""
    return _store.get_history(goal_id)


@router.get('/replay/{goal_id}')
async def replay_goal(goal_id: str):
    """Full replay of a goal's history."""
    return _replay.get_goal_history(goal_id)
