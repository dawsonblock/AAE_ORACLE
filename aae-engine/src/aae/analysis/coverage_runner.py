from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List

import coverage


class CoverageRunner:
    def run(self, code: str) -> Dict[str, Any]:
        cov = coverage.Coverage()
        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                delete=False,
                suffix=".py",
                encoding="utf-8",
            ) as tmp:
                tmp.write(code)
                tmp_path = tmp.name

            cov.start()
            namespace = {}
            try:
                exec(compile(code, tmp_path, "exec"), namespace, namespace)
            except Exception:
                pass
            cov.stop()
            cov.save()

            data = cov.get_data()
            executed: List[int] = list(data.lines(tmp_path) or [])

            return {
                "status": "ok",
                "executed_lines": executed,
            }

        except Exception as exc:
            return {
                "status": "exception",
                "executed_lines": [],
                "error": str(exc),
            }

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
