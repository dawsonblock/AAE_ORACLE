from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter
import time

from aae.oracle_bridge import (
    OraclePlanRequest,
    OraclePlanningBridge,
    ExperimentResultRequest,
    process_experiment_result,
)

router = APIRouter(prefix='/api/oracle', tags=['oracle'])
BRIDGE = OraclePlanningBridge()

# In-memory fusion observability store (Phase 6)
class FusionStatsStore:
    """In-memory store for Oracle-AAE fusion observability metrics."""
    
    def __init__(self):
        self._goals: dict = {}  # goal_id -> goal info
        self._candidates: list = []  # list of candidate rankings
        self._accepted: int = 0
        self._rejected: int = 0
        self._test_passed: int = 0
        self._test_total: int = 0
        self._score_lifts: list = []
        self._fallback_count: int = 0
        self._oracle_native_count: int = 0
        self._aae_advised_count: int = 0
        self._hybrid_count: int = 0
    
    def record_goal(self, goal_id: str, objective: str) -> None:
        """Record an incoming goal from Oracle."""
        self._goals[goal_id] = {
            'goal_id': goal_id,
            'objective': objective,
            'status': 'active',
            'created_at': datetime.utcnow().isoformat(),
            'active_candidates': 0,
        }
    
    def record_candidate_ranking(
        self, 
        goal_id: str, 
        candidate_id: str, 
        predicted_score: float,
        source: str
    ) -> None:
        """Record a candidate ranking."""
        rank = len([c for c in self._candidates if c['goal_id'] == goal_id]) + 1
        self._candidates.append({
            'goal_id': goal_id,
            'candidate_id': candidate_id,
            'predicted_score': predicted_score,
            'source': source,
            'rank': rank,
        })
        # Update source counts
        if source == 'oracle_native':
            self._oracle_native_count += 1
        elif source == 'aae_advised':
            self._aae_advised_count += 1
        elif source == 'hybrid':
            self._hybrid_count += 1
        # Update goal active candidates
        if goal_id in self._goals:
            self._goals[goal_id]['active_candidates'] += 1
    
    def record_acceptance(self, accepted: bool) -> None:
        """Record candidate acceptance/rejection."""
        if accepted:
            self._accepted += 1
        else:
            self._rejected += 1
    
    def record_test_result(self, passed: bool, score_lift: float = 0.0) -> None:
        """Record test execution result."""
        self._test_total += 1
        if passed:
            self._test_passed += 1
        if score_lift != 0.0:
            self._score_lifts.append(score_lift)
    
    def record_fallback(self) -> None:
        """Record fallback to Oracle-native plan."""
        self._fallback_count += 1
    
    def get_stats(self) -> dict:
        """Get current fusion statistics."""
        active_goals = [g for g in self._goals.values() if g['status'] == 'active']
        pending_goals = [g for g in self._goals.values() if g['status'] == 'pending']
        
        total = self._accepted + self._rejected
        avg_score_lift = sum(self._score_lifts) / len(self._score_lifts) if self._score_lifts else 0.0
        fallback_freq = self._fallback_count / (total or 1)
        
        return {
            'incoming_goals': {
                'count': len(self._goals),
                'active': len(active_goals),
                'pending': len(pending_goals),
            },
            'candidate_rankings': self._candidates[-50:],  # Last 50 candidates
            'acceptance_stats': {
                'accepted': self._accepted,
                'rejected': self._rejected,
                'total': total,
            },
            'test_pass_rate': self._test_passed / (self._test_total or 1),
            'average_score_lift': avg_score_lift,
            'fallback_frequency': fallback_freq,
            'source_breakdown': {
                'oracle_native': self._oracle_native_count,
                'aae_advised': self._aae_advised_count,
                'hybrid': self._hybrid_count,
            },
        }

FUSION_STATS = FusionStatsStore()


@router.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok', 'engine': 'aae.oracle_bridge.v1'}


@router.post('/plan')
async def plan(request: OraclePlanRequest):
    # Record goal for observability
    FUSION_STATS.record_goal(request.goal_id, request.objective)
    
    result = BRIDGE.plan(request)
    
    # Record candidates for observability
    for candidate in result.candidates:
        FUSION_STATS.record_candidate_ranking(
            goal_id=request.goal_id,
            candidate_id=candidate.candidate_id,
            predicted_score=candidate.predicted_score,
            source='aae_advised'  # All AAE-provided candidates
        )
    
    return result.model_dump()


@router.post('/experiment_result')
async def receive_experiment_result(
    request: ExperimentResultRequest
) -> dict:
    """Receive experiment execution results and return scoring feedback."""
    result = process_experiment_result(request)
    
    # Record test result for observability
    test_passed = request.test_results.is_success()
    execution_passed = request.execution_status == "success"
    FUSION_STATS.record_test_result(test_passed)
    
    return result.model_dump()


@router.get('/fusion-stats')
async def get_fusion_stats():
    """Get Oracle-AAE fusion observability statistics (Phase 6)."""
    return FUSION_STATS.get_stats()


@router.post('/record-acceptance')
async def record_acceptance(payload: dict):
    """Record candidate acceptance/rejection for observability."""
    accepted = payload.get('accepted', False)
    source = payload.get('source', 'unknown')
    FUSION_STATS.record_acceptance(accepted)
    if not accepted:
        FUSION_STATS.record_fallback()
    return {'status': 'recorded'}


@router.post('/record-fallback')
async def record_fallback():
    """Record fallback to Oracle-native plan."""
    FUSION_STATS.record_fallback()
    return {'status': 'recorded'}
