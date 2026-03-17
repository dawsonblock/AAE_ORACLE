
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# MARK: - Schema Version

CANDIDATE_SCHEMA_VERSION = "aae.oracle_bridge.v1"


# MARK: - Enums

class CandidateKind(str, Enum):
    """Allowed candidate kind values - must match OracleAAECandidateKind in Swift."""
    INSPECT_REPOSITORY = "aae.inspect_repository"
    ANALYZE_OBJECTIVE = "aae.analyze_objective"
    RUN_TARGETED_TESTS = "aae.run_targeted_tests"
    LOCALIZE_FAILURE = "aae.localize_failure"
    GENERATE_PATCH = "aae.generate_patch"
    VALIDATE_CANDIDATE = "aae.validate_candidate"
    ESTIMATE_CHANGE_IMPACT = "aae.estimate_change_impact"

    @classmethod
    def values(cls) -> List[str]:
        return [item.value for item in cls]


class ToolName(str, Enum):
    """Allowed tool name values - must match OracleAAEToolName in Swift."""
    REPOSITORY_ANALYZER = "repository_analyzer"
    PLANNER_SERVICE = "planner_service"
    SANDBOX = "sandbox"
    LOCALIZATION_SERVICE = "localization_service"
    PATCH_ENGINE = "patch_engine"
    VERIFIER = "verifier"
    GRAPH_SERVICE = "graph_service"

    @classmethod
    def values(cls) -> List[str]:
        return [item.value for item in cls]


class SafetyClass(str, Enum):
    """Allowed safety class values - must match OracleAAESafetyClass in Swift."""
    READ_ONLY = "read_only"
    BOUNDED_MUTATION = "bounded_mutation"
    REQUIRES_APPROVAL = "requires_approval"
    SANDBOXED_WRITE = "sandboxed_write"

    @classmethod
    def values(cls) -> List[str]:
        return [item.value for item in cls]


# MARK: - Validation Errors

class CandidateValidationError(Exception):
    """Raised when a candidate fails validation."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Candidate validation failed: {'; '.join(errors)}")


# MARK: - Models

class OraclePlanRequest(BaseModel):
    goal_id: str = Field(default='oracle-goal')
    objective: str
    repo_path: Optional[str] = None
    state_summary: str = ''
    constraints: Dict[str, Any] = Field(default_factory=dict)
    max_candidates: int = Field(default=5, ge=1, le=20)


class OracleCandidateCommand(BaseModel):
    """Candidate command proposed by AAE. Validation is deferred to validate_candidates()."""
    candidate_id: str
    kind: str
    tool: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    rationale: str
    confidence: float
    predicted_score: float
    safety_class: str
    target_file: Optional[str] = None

    def requires_approval(self) -> bool:
        """Check if this candidate requires operator approval."""
        return self.safety_class == SafetyClass.REQUIRES_APPROVAL.value


class OraclePlanResponse(BaseModel):
    goal_id: str
    engine: str = CANDIDATE_SCHEMA_VERSION
    summary: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    candidates: List[OracleCandidateCommand] = Field(default_factory=list)

    def get_requires_approval_candidates(self) -> List[OracleCandidateCommand]:
        """Return all candidates that require operator approval."""
        return [c for c in self.candidates if c.requires_approval()]

    def get_valid_candidates(self) -> List[OracleCandidateCommand]:
        """Return all valid candidates (no validation errors)."""
        return self.candidates


# MARK: - Validation Utility

def validate_candidates(candidates: List[OracleCandidateCommand]) -> Dict[str, Any]:
    """
    Validate a list of candidates at the API boundary.
    
    Returns a validation report with:
    - total_candidates: int
    - valid_candidates: int
    - rejected_candidates: int
    - requires_approval_candidates: List[str]
    - rejection_reasons: Dict[str, List[str]]
    """
    valid = []
    rejected = []
    requires_approval_ids = []
    rejection_reasons: Dict[str, List[str]] = {}

    for candidate in candidates:
        errors: List[str] = []
        
        # Validate kind
        if candidate.kind not in CandidateKind.values():
            errors.append(f"Unknown candidate_kind: \"{candidate.kind}\"")
        
        # Validate tool
        if candidate.tool not in ToolName.values():
            errors.append(f"Unknown tool_name: \"{candidate.tool}\"")
        
        # Validate safety_class
        if candidate.safety_class not in SafetyClass.values():
            errors.append(f"Invalid safety_class: \"{candidate.safety_class}\"")
        
        # Validate rationale
        if not candidate.rationale.strip():
            errors.append("Missing required field: rationale")
        
        # Validate confidence bounds
        if candidate.confidence < 0.0 or candidate.confidence > 1.0:
            errors.append(f"confidence out of bounds: {candidate.confidence}")
        
        if errors:
            rejected.append(candidate)
            rejection_reasons[candidate.candidate_id] = errors
        else:
            valid.append(candidate)
            if candidate.requires_approval():
                requires_approval_ids.append(candidate.candidate_id)

    return {
        "total_candidates": len(candidates),
        "valid_candidates": len(valid),
        "rejected_candidates": len(rejected),
        "requires_approval_candidates": requires_approval_ids,
        "rejection_reasons": rejection_reasons,
        "allRejectionReasons": rejection_reasons,
    }


def validate_response(response: OraclePlanResponse) -> OraclePlanResponse:
    """
    Validate a complete response before sending to Oracle.
    
    This is the API boundary validation - rejects malformed candidates early.
    Adds warnings for rejected candidates and requires_approval candidates.
    """
    validation = validate_candidates(response.candidates)
    
    # Add warning for rejected candidates
    if validation["rejected_candidates"] > 0:
        response.warnings.append(
            f"Warning: {validation['rejected_candidates']} candidates rejected during validation"
        )
    
    # Add warning for requires_approval candidates
    if validation["requires_approval_candidates"]:
        response.warnings.append(
            f"Info: {len(validation['requires_approval_candidates'])} candidates require operator approval: "
            f"{validation['requires_approval_candidates']}"
        )
    
    return response
