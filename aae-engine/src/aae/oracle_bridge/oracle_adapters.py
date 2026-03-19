from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from aae.oracle_bridge.contracts import Candidate, CandidateType, ContractVersion, ExperimentResultRequest, PlanRequest

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


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


class OracleTestResultSummary(BaseModel):
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    total_tests: int = Field(default=0, ge=0)

    def is_success(self) -> bool:
        return self.failed == 0 and self.errors == 0


class OracleBuildResultSummary(BaseModel):
    success: bool = Field(default=False)
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    error_messages: List[str] = Field(default_factory=list)


class OracleSafetyViolation(BaseModel):
    violation_type: str
    severity: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None


class OracleExperimentResultRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    goal_id: str
    candidate_id: str
    candidate_type: str = "patch"
    command_executed: str
    touched_files: List[str] = Field(default_factory=list)
    test_results: OracleTestResultSummary
    build_results: OracleBuildResultSummary
    runtime_diagnostics: List[str] = Field(default_factory=list)
    domain_event_summary: str = ""
    safety_violations: List[OracleSafetyViolation] = Field(default_factory=list)
    elapsed_time_seconds: float = Field(ge=0.0)
    execution_status: str
    trace_id: Optional[str] = None

    def get_execution_status(self) -> ExecutionStatus:
        return ExecutionStatus(self.execution_status)


class CandidateRankingUpdate(BaseModel):
    candidate_id: str
    new_score: float = Field(ge=0.0, le=1.0)
    rank_change: int


class ExperimentResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=1.0)
    failure_mode: Optional[str] = None
    repair_usefulness: str
    feedback_summary: str
    updated_candidate_ranking: Optional[List[CandidateRankingUpdate]] = None


def validate_candidates(candidates: List[OracleCandidateCommand]) -> Dict[str, Any]:
    valid: List[OracleCandidateCommand] = []
    rejected: List[OracleCandidateCommand] = []
    requires_approval_ids: List[str] = []
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
        "valid": valid,
        "rejected": rejected,
        "valid_candidates": len(valid),
        "rejected_candidates": len(rejected),
        "requires_approval_candidates": requires_approval_ids,
        "rejection_reasons": rejection_reasons,
        "allRejectionReasons": rejection_reasons,
    }


def validate_response(response: OraclePlanResponse) -> OraclePlanResponse:
    validation = validate_candidates(response.candidates)
    response.candidates = validation["valid"]
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


def convert_oracle_request(request: OraclePlanRequest) -> PlanRequest:
    target_files = request.constraints.get("target_files") or request.constraints.get("candidate_paths") or []
    source_code = request.state_summary or request.objective
    return PlanRequest(
        version=ContractVersion.V1,
        goal=request.objective,
        source_code=source_code,
        target_files=target_files,
        trace_id=request.trace_id,
    )


def convert_candidate(candidate: Candidate, recommended_test_command: str = "") -> OracleCandidateCommand:
    tool = ToolName.PATCH_ENGINE.value if candidate.type == CandidateType.PATCH else ToolName.PLANNER_SERVICE.value
    kind = CandidateKind.GENERATE_PATCH.value if candidate.type == CandidateType.PATCH else CandidateKind.ANALYZE_OBJECTIVE.value
    return OracleCandidateCommand(
        candidate_id=candidate.id,
        kind=kind,
        tool=tool,
        payload={"candidate_paths": candidate.target_files, "diff": candidate.diff},
        rationale="Canonical candidate generated by the AAE planning pipeline.",
        confidence=candidate.confidence,
        predicted_score=candidate.confidence,
        safety_class=SafetyClass.SANDBOXED_WRITE.value if candidate.type == CandidateType.PATCH else SafetyClass.READ_ONLY.value,
        target_file=candidate.target_files[0] if candidate.target_files else None,
        ranked_fallback_paths=candidate.target_files or None,
        recommended_test_command=recommended_test_command or None,
    )


def convert_oracle_response(
    *,
    goal_id: str,
    candidates: List[Candidate],
    summary: Optional[Dict[str, Any]] = None,
    warnings: Optional[List[str]] = None,
    recommended_test_command: str = "",
    max_candidates: int = 5,
) -> OraclePlanResponse:
    oracle_candidates = [
        convert_candidate(candidate, recommended_test_command=recommended_test_command)
        for candidate in candidates[:max_candidates]
    ]
    response = OraclePlanResponse(
        goal_id=goal_id,
        summary=summary or {},
        warnings=list(warnings or []),
        candidates=oracle_candidates,
    )
    if any(candidate.confidence < 0.9 for candidate in response.candidates):
        response.warnings.append("Low confidence candidates returned")
    return validate_response(response)


def convert_oracle_result_request(request: OracleExperimentResultRequest) -> ExperimentResultRequest:
    execution_status = getattr(request, "execution_status", "failure")
    test_results = getattr(request, "test_results", None)
    build_results = getattr(request, "build_results", None)
    safety_violations = getattr(request, "safety_violations", [])
    test_pass_rate = 0.0
    error_reduction = 0.0
    if test_results is not None:
        total = getattr(test_results, "total_tests", 0) or 0
        failed = getattr(test_results, "failed", 0) or 0
        errors = getattr(test_results, "errors", 0) or 0
        test_pass_rate = (total - failed - errors) / total if total else 0.0
        error_reduction = 1.0 if failed == 0 and errors == 0 else 0.0

    coverage_delta = 1.0 if getattr(request, "domain_event_summary", "").strip() else 0.0
    stability = 0.0 if safety_violations else 1.0
    if execution_status == "success":
        accepted = True
    else:
        accepted = bool(
            test_results is not None
            and getattr(test_results, "is_success", lambda: False)()
            and getattr(build_results, "success", execution_status == "success")
            and not safety_violations
        )
    raw_candidate_type = getattr(request, "candidate_type", CandidateType.PATCH.value)
    try:
        candidate_type = CandidateType(raw_candidate_type)
    except ValueError:
        candidate_type = CandidateType.PATCH

    return ExperimentResultRequest(
        trace_id=getattr(request, "trace_id", None) or "legacy-trace",
        goal=getattr(request, "goal_id", None) or getattr(request, "goal", "repair"),
        candidate_id=getattr(request, "candidate_id", ""),
        candidate_type=candidate_type,
        target_files=getattr(request, "touched_files", []) or getattr(request, "target_files", []),
        accepted=accepted,
        execution_result=execution_status,
        metrics={
            "test_pass_rate": test_pass_rate,
            "error_reduction": error_reduction,
            "coverage_delta": coverage_delta,
            "stability": stability,
            "elapsed_time_seconds": getattr(request, "elapsed_time_seconds", 0.0),
            "runtime_diagnostics": getattr(request, "runtime_diagnostics", []),
            "domain_event_summary": getattr(request, "domain_event_summary", ""),
            "build_success": getattr(build_results, "success", False) if build_results is not None else False,
            "safety_violations": [violation.model_dump() for violation in safety_violations],
        },
    )
