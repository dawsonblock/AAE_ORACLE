from __future__ import annotations

from typing import Any, Dict, List

from aae.agents.base_agent import BaseAgent


class TestAgent(BaseAgent):
    """Autonomous test execution and validation agent.

    Runs the target test suite inside the sandbox, collects results,
    and determines whether the fail-to-pass acceptance criterion is met.
    The TestAgent is invoked by the controller both *before* a patch
    (to establish the baseline failure set) and *after* (to validate the fix).
    """

    name = "test"
    domain = "validation"

    async def run(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        action = task.get("action", "run_tests")
        if action == "run_tests":
            return await self.run_tests(task, context)
        if action == "collect_coverage":
            return await self.collect_coverage(task, context)
        if action == "validate_patch":
            return await self.validate_patch(task, context)
        if action == "baseline":
            return await self.establish_baseline(task, context)
        return {"status": "unknown_action", "action": action}

    async def run_tests(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        repo_path = context.get("repo_path", ".")
        test_ids: List[str] = task.get("test_ids", [])
        cmd = self._build_command(repo_path, test_ids)

        try:
            from aae.sandbox.sandbox_manager import SandboxManager
            mgr = SandboxManager()
            result = await mgr.run_job(cmd, repo_path)
            passed, failed = self._parse_results(result.get("stdout", ""))
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        return {
            "status": "complete",
            "command": cmd,
            "passed": passed,
            "failed": failed,
            "returncode": result.get("returncode", -1),
            "stdout": result.get("stdout", "")[:4000],
        }

    async def collect_coverage(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        repo_path = context.get("repo_path", ".")
        cmd = "pytest --cov=. --cov-report=json:coverage.json -q"
        try:
            from aae.sandbox.sandbox_manager import SandboxManager
            mgr = SandboxManager()
            result = await mgr.run_job(cmd, repo_path)
            coverage_path = result.get("coverage_path", "")
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        return {
            "status": "coverage_collected",
            "coverage_path": coverage_path,
            "returncode": result.get("returncode", -1),
        }

    async def validate_patch(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Confirm fail-to-pass tests now pass and no regressions introduced."""
        baseline_failures: List[str] = task.get("baseline_failures", [])
        result = await self.run_tests(task, context)
        if result.get("status") == "error":
            return result

        now_passed = result.get("passed", [])
        now_failed = result.get("failed", [])

        fixed = [t for t in baseline_failures if t in now_passed]
        regressed = [t for t in now_failed if t not in baseline_failures]

        success = len(fixed) > 0 and len(regressed) == 0
        return {
            "status": "validated",
            "success": success,
            "fixed_tests": fixed,
            "regressed_tests": regressed,
            "baseline_failures": baseline_failures,
        }

    async def establish_baseline(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run full test suite and capture the initial failure set."""
        result = await self.run_tests(task, context)
        baseline = result.get("failed", [])
        context["baseline_failures"] = baseline
        return {
            "status": "baseline_established",
            "failing_count": len(baseline),
            "baseline_failures": baseline,
        }

    # ── helpers ───────────────────────────────────────────────────────────────

    def _build_command(self, repo_path: str, test_ids: List[str]) -> str:
        if test_ids:
            ids = " ".join(test_ids[:20])
            return "pytest %s -v --tb=short" % ids
        return "pytest -v --tb=short"

    def _parse_results(self, stdout: str) -> tuple[List[str], List[str]]:
        passed: List[str] = []
        failed: List[str] = []
        for line in stdout.splitlines():
            if " PASSED" in line:
                passed.append(line.split()[0])
            elif " FAILED" in line:
                failed.append(line.split()[0])
        return passed, failed
