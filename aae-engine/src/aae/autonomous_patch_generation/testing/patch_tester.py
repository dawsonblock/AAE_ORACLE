"""autonomous_patch_generation/testing/patch_tester — run tests on a patch."""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class TestRun:
    """Result of running tests against a patch."""

    patch_id: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    total: int = 0
    duration_s: float = 0.0
    output: str = ""
    fail_to_pass: List[str] = field(default_factory=list)
    pass_to_fail: List[str] = field(default_factory=list)
    success: bool = False

    def pass_rate(self) -> float:
        if not self.total:
            return 0.0
        return self.passed / self.total


class PatchTester:
    """Run the test suite after a patch is applied and parse the result.

    Parameters
    ----------
    repo_root:
        Root of the repository.
    test_command:
        Shell command to run tests (default: ``pytest -x --tb=short``).
    timeout:
        Maximum seconds to wait for tests.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        test_command: str = "pytest -x --tb=short -q",
        timeout: int = 120,
    ) -> None:
        self._root = repo_root or Path(".")
        self._cmd = test_command
        self._timeout = timeout

    def run(self, patch_id: str, test_ids: Optional[List[str]] = None) -> TestRun:
        cmd = self._cmd
        if test_ids:
            cmd += " " + " ".join(test_ids)
        run = TestRun(patch_id=patch_id)
        try:
            import time
            t0 = time.monotonic()
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(self._root),
                timeout=self._timeout,
            )
            run.duration_s = round(time.monotonic() - t0, 2)
            run.output = (result.stdout + result.stderr)[:4000]
            self._parse_pytest(run, result.stdout)
            run.success = result.returncode == 0
        except subprocess.TimeoutExpired:
            run.output = f"Tests timed out after {self._timeout}s"
        except Exception as exc:
            run.output = str(exc)
        return run

    def compare(
        self, baseline: TestRun, after: TestRun
    ) -> tuple:
        """Return (fail_to_pass, pass_to_fail) sets."""
        baseline_pass = set(self._extract_ids(baseline.output, "PASSED"))
        after_pass = set(self._extract_ids(after.output, "PASSED"))
        baseline_fail = set(self._extract_ids(baseline.output, "FAILED"))
        after_fail = set(self._extract_ids(after.output, "FAILED"))
        ftp = list(baseline_fail & after_pass)
        ptf = list(baseline_pass & after_fail)
        return ftp, ptf

    @staticmethod
    def _parse_pytest(run: TestRun, output: str) -> None:
        import re
        m = re.search(
            r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) error)?",
            output,
        )
        if m:
            run.passed = int(m.group(1) or 0)
            run.failed = int(m.group(2) or 0)
            run.errors = int(m.group(3) or 0)
            run.total = run.passed + run.failed + run.errors

    @staticmethod
    def _extract_ids(output: str, status: str) -> List[str]:
        import re
        return re.findall(rf"([\w/::]+)\s+{status}", output)
