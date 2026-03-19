
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional

from aae.oracle_bridge.result_contracts import (
    ExperimentResultRequest,
    ExperimentResultResponse,
    CandidateRankingUpdate,
    ExecutionStatus,
    RepairUsefulness,
    FailureMode,
)
from aae.storage.experiment_store import ExperimentStore
from aae.storage.ranking_store import RankingStore
from aae.analysis.structured_logger import StructuredEventLogger

logger = logging.getLogger(__name__)

# Scoring policy constants
ACCEPTANCE_THRESHOLD = 0.4
FAILURE_PENALTY = -0.5


# MARK: - In-Memory Ranking Store (legacy fallback)

class CandidateRankingStore:
    """In-memory store for candidate rankings — kept for backward compatibility."""
    
    def __init__(self):
        # Maps goal_id -> list of (candidate_id, score)
        self._rankings: Dict[str, List[Dict]] = {}
    
    def update_ranking(self, goal_id: str, candidate_id: str, new_score: float) -> int:
        """Update a candidate's score and return rank change."""
        if goal_id not in self._rankings:
            self._rankings[goal_id] = []
        
        # Find current rank
        current_rank = None
        rankings = self._rankings[goal_id]
        for i, entry in enumerate(rankings):
            if entry["candidate_id"] == candidate_id:
                current_rank = i
                break
        
        # Add or update entry
        if current_rank is not None:
            old_score = rankings[current_rank]["score"]
            rankings[current_rank]["score"] = new_score
        else:
            rankings.append({"candidate_id": candidate_id, "score": new_score})
            current_rank = len(rankings) - 1
        
        # Sort by score descending
        rankings.sort(key=lambda x: x["score"], reverse=True)
        
        # Find new rank
        new_rank = None
        for i, entry in enumerate(rankings):
            if entry["candidate_id"] == candidate_id:
                new_rank = i
                break
        
        return current_rank - new_rank  # positive = improved
    
    def get_rankings(self, goal_id: str) -> List[Dict]:
        """Get current rankings for a goal."""
        return self._rankings.get(goal_id, [])


# Global ranking store instance (in-memory fallback)
_ranking_store = CandidateRankingStore()


# MARK: - Rejection Telemetry

class RejectionTelemetry:
    """Tracks rejection metrics for observability."""

    def __init__(self):
        self.accepted: int = 0
        self.rejected: int = 0
        self.rejection_reasons: Dict[str, int] = defaultdict(int)

    def record_acceptance(self) -> None:
        self.accepted += 1

    def record_rejection(self, reason: str) -> None:
        self.rejected += 1
        self.rejection_reasons[reason] += 1

    def get_stats(self) -> Dict:
        return {
            "accepted": self.accepted,
            "rejected": self.rejected,
            "total": self.accepted + self.rejected,
            "rejection_reasons": dict(self.rejection_reasons),
        }


# Global telemetry instance
_telemetry = RejectionTelemetry()


def get_telemetry() -> RejectionTelemetry:
    return _telemetry


# MARK: - Result Processing Service

class ExperimentResultService:
    """Service for processing experiment results and scoring."""
    
    def __init__(
        self,
        ranking_store: Optional[CandidateRankingStore] = None,
        experiment_store: Optional[ExperimentStore] = None,
        persistent_ranking_store: Optional[RankingStore] = None,
        event_logger: Optional[StructuredEventLogger] = None,
    ):
        self._ranking_store = ranking_store or _ranking_store
        self._experiment_store = experiment_store
        self._persistent_ranking_store = persistent_ranking_store
        self._event_logger = event_logger
    
    def process_experiment_result(
        self, request: ExperimentResultRequest
    ) -> ExperimentResultResponse:
        """
        Process an experiment result and return scoring feedback.
        
        Steps:
        1. Score the attempt based on test results, build results, etc.
        2. Classify failure mode if failed
        3. Record repair usefulness
        4. Update candidate ranking priors based on outcome
        5. Persist to experiment store
        6. Log structured event
        7. Return feedback summary
        """
        logger.info(f"Processing experiment result for goal={request.goal_id}, "
                   f"candidate={request.candidate_id}, "
                   f"status={request.execution_status}")
        
        # Step 1: Calculate base score
        score = self._calculate_score(request)
        
        # Step 2: Classify failure mode if failed
        failure_mode = self._classify_failure_mode(request)
        
        # Step 3: Assess repair usefulness
        repair_usefulness = self._assess_repair_usefulness(request, score)
        
        # Step 4: Update candidate rankings (in-memory)
        ranking_updates = self._update_rankings(request, score)

        # Step 5: Persist to stores
        trace_id = getattr(request, "trace_id", None)
        self._persist_result(request, score, failure_mode, repair_usefulness, trace_id)
        
        # Step 6: Log structured event
        self._log_event(request, score, failure_mode, trace_id)

        # Step 7: Update telemetry
        if score >= ACCEPTANCE_THRESHOLD:
            _telemetry.record_acceptance()
        else:
            reason = failure_mode or "low_score"
            _telemetry.record_rejection(reason)
        
        # Step 8: Generate feedback summary
        feedback_summary = self._generate_feedback_summary(request, score, failure_mode)
        
        return ExperimentResultResponse(
            score=score,
            failure_mode=failure_mode,
            repair_usefulness=repair_usefulness,
            feedback_summary=feedback_summary,
            updated_candidate_ranking=ranking_updates
        )

    def _persist_result(
        self,
        request: ExperimentResultRequest,
        score: float,
        failure_mode: Optional[str],
        repair_usefulness: str,
        trace_id: Optional[str],
    ) -> None:
        """Persist experiment result to SQLite store."""
        if self._experiment_store:
            self._experiment_store.log(
                goal=request.goal_id,
                candidate_id=request.candidate_id,
                result=request.execution_status,
                score=score,
                failure_mode=failure_mode,
                repair_usefulness=repair_usefulness,
                trace_id=trace_id,
            )
        if self._persistent_ranking_store:
            delta = score if request.execution_status == "success" else FAILURE_PENALTY
            self._persistent_ranking_store.update(
                request.candidate_id, request.goal_id, delta
            )

    def _log_event(
        self,
        request: ExperimentResultRequest,
        score: float,
        failure_mode: Optional[str],
        trace_id: Optional[str],
    ) -> None:
        """Log a structured event for the result."""
        if self._event_logger:
            self._event_logger.log_result(
                goal_id=request.goal_id,
                trace_id=trace_id or "",
                candidate_id=request.candidate_id,
                result=request.execution_status,
                score=score,
                latency_ms=request.elapsed_time_seconds * 1000,
            )

    def _calculate_score(self, request: ExperimentResultRequest) -> float:
        """
        Calculate a score for the experiment outcome.
        
        Scoring algorithm:
        - Base: 0.0
        - Build success: +0.3
        - Tests passed: +0.4 * (passed / total) if total > 0
        - No safety violations: +0.3
        """
        score = 0.0
        
        # Build success contributes 0.3
        if request.build_results.success:
            score += 0.3
        
        # Test results contribute up to 0.4
        test_results = request.test_results
        if test_results.total_tests > 0:
            test_ratio = test_results.passed / test_results.total_tests
            score += 0.4 * test_ratio
        elif test_results.is_success():
            # If there were tests and they all passed
            score += 0.4
        
        # No safety violations contributes 0.3
        if not request.safety_violations:
            score += 0.3
        
        return min(1.0, score)
    
    def _classify_failure_mode(self, request: ExperimentResultRequest) -> Optional[str]:
        """Classify the failure mode if the experiment failed."""
        exec_status = request.get_execution_status()
        
        if exec_status == ExecutionStatus.SUCCESS:
            return None
        
        # Check build results first
        if not request.build_results.success and request.build_results.error_count > 0:
            return FailureMode.BUILD_ERROR.value
        
        # Check test failures
        if request.test_results.failed > 0 or request.test_results.errors > 0:
            return FailureMode.TEST_FAILURE.value
        
        # Check safety violations
        if request.safety_violations:
            return FailureMode.SAFETY_VIOLATION.value
        
        # Check runtime diagnostics for errors
        runtime_errors = [d for d in request.runtime_diagnostics 
                        if "error" in d.lower() or "exception" in d.lower()]
        if runtime_errors:
            return FailureMode.RUNTIME_ERROR.value
        
        # Check for timeout
        if request.elapsed_time_seconds > 300:  # 5 minutes
            return FailureMode.TIMEOUT.value
        
        return FailureMode.UNKNOWN.value
    
    def _assess_repair_usefulness(
        self, request: ExperimentResultRequest, score: float
    ) -> str:
        """
        Assess how useful this repair attempt is for learning.
        
        High: Score improved significantly OR we learned something from failure
        Medium: Partial success or minor improvement
        Low: Complete failure with no useful information
        """
        # If successful with good score, it's highly useful
        if score >= 0.8:
            return RepairUsefulness.HIGH.value
        
        # If partial success, medium usefulness
        if score >= 0.4:
            return RepairUsefulness.MEDIUM.value
        
        # If failed but we have diagnostic info, still useful
        if request.runtime_diagnostics or request.build_results.error_messages:
            return RepairUsefulness.MEDIUM.value
        
        # Complete failure with no info
        return RepairUsefulness.LOW.value
    
    def _update_rankings(
        self, request: ExperimentResultRequest, score: float
    ) -> List[CandidateRankingUpdate]:
        """Update candidate rankings based on the outcome."""
        rank_change = self._ranking_store.update_ranking(
            request.goal_id, 
            request.candidate_id, 
            score
        )
        
        return [CandidateRankingUpdate(
            candidate_id=request.candidate_id,
            new_score=score,
            rank_change=rank_change
        )]
    
    def _generate_feedback_summary(
        self, 
        request: ExperimentResultRequest, 
        score: float,
        failure_mode: Optional[str]
    ) -> str:
        """Generate a human-readable feedback summary."""
        exec_status = request.get_execution_status()
        
        parts = []
        
        # Status summary
        if exec_status == ExecutionStatus.SUCCESS:
            parts.append(f"Experiment SUCCEEDED with score {score:.2f}")
        elif exec_status == ExecutionStatus.PARTIAL:
            parts.append(f"Experiment PARTIALLY SUCCEEDED with score {score:.2f}")
        else:
            parts.append(f"Experiment FAILED with score {score:.2f}")
        
        # Build summary
        if request.build_results.success:
            parts.append("Build completed successfully")
        else:
            parts.append(f"Build failed with {request.build_results.error_count} errors")
        
        # Test summary
        tr = request.test_results
        if tr.total_tests > 0:
            parts.append(
                f"Tests: {tr.passed}/{tr.total_tests} passed, "
                f"{tr.failed} failed, {tr.errors} errors"
            )
        
        # Safety violations
        if request.safety_violations:
            parts.append(
                f"{len(request.safety_violations)} safety violation(s) detected"
            )
        
        # Failure mode
        if failure_mode:
            parts.append(f"Failure mode: {failure_mode}")
        
        # Performance
        if request.elapsed_time_seconds > 0:
            parts.append(f"Execution time: {request.elapsed_time_seconds:.1f}s")
        
        return "; ".join(parts)


# Note:
# The previous global `_experiment_result_service` instance and
# `process_experiment_result` convenience function have been removed
# to avoid using a default-constructed `ExperimentResultService`
# without persistence or structured logging configured.
# Callers should instead instantiate `ExperimentResultService` with
# the appropriate stores/logger and invoke
# `service.process_experiment_result(request)` directly.

ResultService = ExperimentResultService

