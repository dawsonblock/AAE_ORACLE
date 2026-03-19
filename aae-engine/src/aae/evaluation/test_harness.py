from __future__ import annotations

import subprocess
import time
from typing import Dict


class TestHarness:
    def run(self, path: str, timeout: int = 30) -> Dict:
        start = time.perf_counter()

        try:
            proc = subprocess.run(
                ["pytest", path, "-q"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "status": "success" if proc.returncode == 0 else "failure",
                "output": proc.stdout,
                "errors": proc.stderr,
                "returncode": proc.returncode,
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
