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
    target_files: List[str] = Field(default_factory=list)
    accepted: bool
    execution_result: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
