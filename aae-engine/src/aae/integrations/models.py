from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntegrationTaskRequest(BaseModel):
    task_id: str
    objective: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    preferred_tool: Optional[str] = None
    user_message: str = ''
    repo_path: Optional[str] = None
    priority: int = 5


class SecurityFinding(BaseModel):
    severity: str
    category: str
    message: str
    evidence: str = ''
    auto_fixable: bool = False


class SecurityReport(BaseModel):
    allowed: bool
    score: int
    grade: str
    findings: List[SecurityFinding] = Field(default_factory=list)
    engine: str = 'agentshield-bridge'


class MemorySearchHit(BaseModel):
    source: str
    score: float
    session_id: Optional[str] = None
    title: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkerStatus(BaseModel):
    worker_id: str
    capability: str
    completed: int = 0
    busy: bool = False


class IntegrationRunResult(BaseModel):
    task_id: str
    status: str
    selected_tool: str
    selected_worker: str
    security: SecurityReport
    action_result: Dict[str, Any]
    evaluation: Dict[str, Any]
    improvement: Dict[str, Any]
    memory_summary: Dict[str, Any]
