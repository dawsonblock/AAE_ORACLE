from __future__ import annotations

import os
import subprocess
from shutil import which
import tempfile
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from aae.execution.execution_guard import ExecutionGuard


@dataclass
class ExecutionResult:
    status: str
    stdout: str
    stderr: str
    returncode: int
    error: Optional[str]
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SandboxAdapter:
    def __init__(self, python_bin: str | None = None) -> None:
        self.python_bin = python_bin or which("python") or which("python3") or "python3"

    def run(self, code: str, timeout: int = 10, context: str = "sandbox") -> Dict[str, Any]:
        ExecutionGuard.assert_sandbox(context)
        start = time.perf_counter()
        tmp_path = None

        if len(code) > 20000:
            return {
                "status": "rejected",
                "stdout": "",
                "stderr": "",
                "returncode": -1,
                "error": "code too large",
                "latency_ms": 0.0,
            }

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                suffix=".py",
                encoding="utf-8",
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            proc = subprocess.run(
                [self.python_bin, tmp_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            result = ExecutionResult(
                status="success" if proc.returncode == 0 else "error",
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                error=None,
                latency_ms=(time.perf_counter() - start) * 1000.0,
            )
            return result.to_dict()

        except Exception as exc:
            result = ExecutionResult(
                status="exception",
                stdout="",
                stderr="",
                returncode=-1,
                error=str(exc),
                latency_ms=(time.perf_counter() - start) * 1000.0,
            )
            return result.to_dict()

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
