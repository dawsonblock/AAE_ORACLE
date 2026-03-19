from __future__ import annotations

import time
from typing import Dict

from aae.execution.sandbox_adapter import SandboxAdapter


class TestHarness:
    def __init__(self) -> None:
        self.sandbox = SandboxAdapter()

    def run(self, path: str, timeout: int = 30) -> Dict:
        start = time.perf_counter()

        try:
            result = self.sandbox.run(
                "\n".join(
                    [
                        "import os",
                        "import sys",
                        "import pytest",
                        f"os.chdir({path!r})",
                        "raise SystemExit(pytest.main(['-q']))",
                    ]
                ),
                timeout=timeout,
            )
            return {
                "status": "success" if result["returncode"] == 0 else "failure",
                "output": result["stdout"],
                "errors": result["stderr"],
                "returncode": result["returncode"],
                "latency_ms": (time.perf_counter() - start) * 1000.0,
            }
        except Exception as exc:
            return {
                "status": "exception",
                "output": "",
                "errors": "",
                "returncode": -1,
                "error": str(exc),
                "latency_ms": (time.perf_counter() - start) * 1000.0,
            }
