"""execution_manager — high-level coordinator for all code execution requests.

Agents must not spawn processes directly. Instead, they call
``ExecutionManager.execute()``, which selects the appropriate backend
(sandbox container, local subprocess, or dry-run stub) based on the
environment and the request's isolation requirements.
"""
from __future__ import annotations

import asyncio
import logging
import shlex
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class ExecBackend(str, Enum):
    SANDBOX = "sandbox"
    LOCAL = "local"
    DRY_RUN = "dry_run"


class ExecStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ExecRequest:
    kind: str                      # "test" | "code" | "command" | "script"
    payload: Dict[str, Any]        # kind-specific parameters
    isolation: bool = True         # require container isolation?
    timeout: float = 120.0         # seconds
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ExecResult:
    task_id: str
    status: ExecStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    artifacts: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    error: Optional[str] = None

    def ok(self) -> bool:
        return self.status == ExecStatus.SUCCESS


class ExecutionManager:
    """Select and invoke the correct execution backend for each request.

    Falls back gracefully::

        sandbox  →  local subprocess  →  dry-run stub
    """

    def __init__(
        self,
        sandbox_manager: Any | None = None,
        local_allowed: bool = True,
        dry_run: bool = False,
    ) -> None:
        self._sandbox = sandbox_manager
        self._local_allowed = local_allowed
        self._dry_run = dry_run
        self._history: List[ExecResult] = []

    async def execute(self, request: ExecRequest) -> ExecResult:
        """Route *request* to the right backend and return an ExecResult."""
        t0 = time.perf_counter()
        backend = self._select_backend(request)
        log.info(
            "exec task_id=%s kind=%s backend=%s",
            request.task_id,
            request.kind,
            backend,
        )
        try:
            result = await asyncio.wait_for(
                self._dispatch(request, backend),
                timeout=request.timeout,
            )
        except asyncio.TimeoutError:
            result = ExecResult(
                task_id=request.task_id,
                status=ExecStatus.TIMEOUT,
                error=f"Timed out after {request.timeout}s",
            )
        except Exception as exc:
            result = ExecResult(
                task_id=request.task_id,
                status=ExecStatus.FAILED,
                error=str(exc),
            )
        result.elapsed_ms = (time.perf_counter() - t0) * 1000
        self._history.append(result)
        return result

    def history(self, limit: int = 50) -> List[ExecResult]:
        return self._history[-limit:]

    def stats(self) -> Dict[str, Any]:
        total = len(self._history)
        success = sum(1 for r in self._history if r.ok())
        return {
            "total": total,
            "success": success,
            "failed": total - success,
        }

    # ── backend selection ─────────────────────────────────────────────────────

    def _select_backend(self, req: ExecRequest) -> ExecBackend:
        if self._dry_run:
            return ExecBackend.DRY_RUN
        if req.isolation and self._sandbox:
            return ExecBackend.SANDBOX
        if self._local_allowed:
            return ExecBackend.LOCAL
        return ExecBackend.DRY_RUN

    async def _dispatch(
        self, req: ExecRequest, backend: ExecBackend
    ) -> ExecResult:
        if backend == ExecBackend.SANDBOX:
            return await self._run_sandbox(req)
        if backend == ExecBackend.LOCAL:
            return await self._run_local(req)
        return self._run_dry(req)

    # ── backends ──────────────────────────────────────────────────────────────

    async def _run_sandbox(self, req: ExecRequest) -> ExecResult:
        command = self._build_command(req)
        raw = await self._sandbox.execute(
            command=command,
            image=req.payload.get("image", "python:3.11-slim"),
            env=req.payload.get("env", {}),
        )
        return ExecResult(
            task_id=req.task_id,
            status=(
                ExecStatus.SUCCESS
                if (raw or {}).get("exit_code", 1) == 0
                else ExecStatus.FAILED
            ),
            stdout=(raw or {}).get("stdout", ""),
            stderr=(raw or {}).get("stderr", ""),
            exit_code=(raw or {}).get("exit_code", 1),
        )

    async def _run_local(self, req: ExecRequest) -> ExecResult:
        args = self._build_args(req)
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        code = proc.returncode or 0
        return ExecResult(
            task_id=req.task_id,
            status=ExecStatus.SUCCESS if code == 0 else ExecStatus.FAILED,
            stdout=stdout_b.decode(errors="replace"),
            stderr=stderr_b.decode(errors="replace"),
            exit_code=code,
        )

    @staticmethod
    def _run_dry(req: ExecRequest) -> ExecResult:
        log.debug("dry-run exec: %s", req.task_id)
        return ExecResult(
            task_id=req.task_id,
            status=ExecStatus.SUCCESS,
            stdout=f"[dry-run] would execute kind={req.kind}",
        )

    @staticmethod
    def _build_command(req: ExecRequest) -> str:
        if req.kind == "test":
            tests = " ".join(req.payload.get("test_ids", []))
            return f"python -m pytest {tests} -x --tb=short"
        if req.kind == "script":
            return str(req.payload.get("script_path", ""))
        if req.kind == "command":
            return str(req.payload.get("command", "echo done"))
        if req.kind == "code":
            code = req.payload.get("code", "")
            escaped = code.replace("'", "'\\''")
            return f"python -c '{escaped}'"
        return "echo unknown"

    @staticmethod
    def _build_args(req: ExecRequest) -> list[str]:
        """Build a safe argument list for subprocess execution without shell."""
        if req.kind == "test":
            test_ids = req.payload.get("test_ids", [])
            return ["python", "-m", "pytest", *test_ids, "-x", "--tb=short"]
        if req.kind == "script":
            return ["python", str(req.payload.get("script_path", ""))]
        if req.kind == "command":
            # shlex.split avoids shell interpretation; callers must only pass
            # trusted command strings since arbitrary command execution is
            # inherently privileged.
            return shlex.split(req.payload.get("command", "echo done"))
        if req.kind == "code":
            return ["python", "-c", req.payload.get("code", "")]
        return ["echo", f"unknown request kind: {req.kind}"]
