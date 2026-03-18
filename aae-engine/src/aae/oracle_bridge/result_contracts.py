
from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


# MARK: - Schema Version

RESULT_SCHEMA_VERSION = "aae.result.v1"


# MARK: - Enums

class ExecutionStatus(str, Enum):
    """Execution status values - must match ExecutionStatus in Swift."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


class RepairUsefulness(str, Enum):
    """How useful was this repair attempt for learning."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FailureMode(str, Enum):
    """Classified failure modes for failed experiments."""
    BUILD_ERROR = "build_error"
    TEST_FAILURE = "test_failure"
    RUNTIME_ERROR = "runtime_error"
    SAFETY_VIOLATION = "safety_violation"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# MARK: - Request Models

class TestResultSummary(BaseModel):
    """Test result summary - matches TestResultSummary in Swift."""
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    total_tests: int = Field(default=0, ge=0)

    def is_success(self) -> bool:
        return self.failed == 0 and self.errors == 0


class BuildResultSummary(BaseModel):
    """Build result summary - matches BuildResultSummary in Swift."""
    success: bool = Field(default=False)
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    error_messages: List[str] = Field(default_factory=list)


class SafetyViolation(BaseModel):
    """Safety violation record - matches SafetyViolation in Swift."""
    violation_type: str
    severity: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None


class ExperimentResultRequest(BaseModel):
    """Request schema for experiment result submission."""
    goal_id: str
    candidate_id: str
    command_executed: str
    touched_files: List[str] = Field(default_factory=list)
    test_results: TestResultSummary
    build_results: BuildResultSummary
    runtime_diagnostics: List[str] = Field(default_factory=list)
    domain_event_summary: str = ""
    safety_violations: List[SafetyViolation] = Field(default_factory=list)
    elapsed_time_seconds: float = Field(ge=0.0)
    execution_status: str  # success, partial, failure
    trace_id: Optional[str] = None

    def get_execution_status(self) -> ExecutionStatus:
        """Convert string to ExecutionStatus enum."""
        return ExecutionStatus(self.execution_status)


# MARK: - Response Models

class CandidateRankingUpdate(BaseModel):
    """Candidate ranking update - matches CandidateRankingUpdate in Swift."""
    candidate_id: str
    new_score: float = Field(ge=0.0, le=1.0)
    rank_change: int  # positive = improved, negative = dropped


class ExperimentResultResponse(BaseModel):
    """Response schema for experiment result processing."""
    score: float = Field(ge=0.0, le=1.0)
    failure_mode: Optional[str] = None  # null if success
    repair_usefulness: str  # high, medium, low
    feedback_summary: str
    updated_candidate_ranking: Optional[List[CandidateRankingUpdate]] = None

    def model_dump(self, **kwargs) -> dict:
        """Override to handle Optional fields properly."""
        return {
            "score": self.score,
            "failure_mode": self.failure_mode,
            "repair_usefulness": self.repair_usefulness,
            "feedback_summary": self.feedback_summary,
            "updated_candidate_ranking": (
                [r.model_dump() for r in self.updated_candidate_ranking]
                if self.updated_candidate_ranking else None
            )
        }
