from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ContractVersion(str, Enum):
    V1 = "v1"


class CandidateType(str, Enum):
    PATCH = "patch"
    REFACTOR = "refactor"
    CONFIG = "config"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = ContractVersion.V1
    goal: str
    source_code: str
    target_files: List[str] = Field(default_factory=list)
    trace_id: Optional[str] = None


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: CandidateType
    confidence: float
    risk: RiskLevel
    target_files: List[str]
    diff: str
    trace_id: Optional[str] = None


class ExperimentResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: ContractVersion = ContractVersion.V1
    trace_id: str
    goal: str
    candidate_id: str
    candidate_type: CandidateType
    target_files: List[str]
    accepted: bool
    execution_result: str
    metrics: dict


CANDIDATE_SCHEMA_VERSION = "aae.oracle_bridge.v1"


class CandidateKind(str, Enum):
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
    READ_ONLY = "read_only"
    BOUNDED_MUTATION = "bounded_mutation"
    REQUIRES_APPROVAL = "requires_approval"
    SANDBOXED_WRITE = "sandboxed_write"

    @classmethod
    def values(cls) -> List[str]:
        return [item.value for item in cls]


class OraclePlanRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: str = ContractVersion.V1.value
    goal_id: str = "oracle-goal"
    objective: str
    repo_path: Optional[str] = None
    state_summary: str = ""
    constraints: Dict[str, Any] = Field(default_factory=dict)
    max_candidates: int = Field(default=5, ge=1, le=20)
    trace_id: Optional[str] = None


class OracleCandidateCommand(BaseModel):
    model_config = ConfigDict(extra="allow")

    candidate_id: str
    kind: str
    tool: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    rationale: str
    confidence: float
    predicted_score: float
    safety_class: str
    target_file: Optional[str] = None
    ranked_fallback_paths: Optional[List[str]] = None
    recommended_test_command: Optional[str] = None
    dominant_language: Optional[str] = None
    patch_file_count_limit: Optional[int] = None

    def requires_approval(self) -> bool:
        return self.safety_class == SafetyClass.REQUIRES_APPROVAL.value


class OraclePlanResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    goal_id: str
    engine: str = CANDIDATE_SCHEMA_VERSION
    summary: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    candidates: List[OracleCandidateCommand] = Field(default_factory=list)


def validate_candidates(candidates: List[OracleCandidateCommand]) -> Dict[str, Any]:
    valid = []
    rejected = []
    requires_approval_ids = []
    rejection_reasons: Dict[str, List[str]] = {}

    for candidate in candidates:
        errors: List[str] = []
        if candidate.kind not in CandidateKind.values():
            errors.append(f'Unknown candidate_kind: "{candidate.kind}"')
        if candidate.tool not in ToolName.values():
            errors.append(f'Unknown tool_name: "{candidate.tool}"')
        if candidate.safety_class not in SafetyClass.values():
            errors.append(f'Invalid safety_class: "{candidate.safety_class}"')
        if not candidate.rationale.strip():
            errors.append("Missing required field: rationale")
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
    validation = validate_candidates(response.candidates)
    if validation["rejected_candidates"] > 0:
        response.warnings.append(
            f"Warning: {validation['rejected_candidates']} candidates rejected during validation"
        )
    if validation["requires_approval_candidates"]:
        response.warnings.append(
            f"Info: {len(validation['requires_approval_candidates'])} candidates require operator approval: "
            f"{validation['requires_approval_candidates']}"
        )
    return response
