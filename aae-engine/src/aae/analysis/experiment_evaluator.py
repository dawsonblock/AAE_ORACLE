"""Authoritative experiment evaluator for AAE runtime scoring."""
from __future__ import annotations

from typing import Any, Dict

EXPECTED_ARTIFACT_COUNT = 5.0


class ExperimentEvaluator:
    """Score experiment outcomes deterministically from canonical metrics."""

    def evaluate(self, goal: str, result: Dict[str, Any]) -> Dict[str, Any]:
        status = result.get("status") or result.get("execution_result", "failure")
        violations = result.get("safety_violations", [])
        metrics: Dict[str, float] = {
            "success": 1.0 if status == "success" else 0.0,
            "no_exceptions": 1.0 if not result.get("exception") else 0.0,
            "test_pass_rate": self._test_pass_rate(result),
            "error_reduction": self._error_reduction(result, status),
            "coverage_delta": self._coverage_delta(result),
            "stability": self._stability(result, violations),
            "safety_score": 1.0 if not violations else 0.0,
        }
        primary = (
            metrics["test_pass_rate"],
            metrics["error_reduction"],
            metrics["coverage_delta"],
            metrics["stability"],
        )
        score = sum(primary) / len(primary)

        return {
            "score": round(score, 4),
            "metrics": metrics,
        }

    def _test_pass_rate(self, result: Dict[str, Any]) -> float:
        if "test_pass_rate" in result:
            return float(result["test_pass_rate"])
        test_passed = result.get("tests_passed", 0)
        test_total = result.get("tests_total", 0)
        if isinstance(test_passed, bool):
            return 1.0 if test_passed else 0.0
        if test_total:
            return max(0.0, min(float(test_passed) / float(test_total), 1.0))
        return 0.0

    def _error_reduction(self, result: Dict[str, Any], status: str) -> float:
        if "error_reduction" in result:
            return float(result["error_reduction"])
        return 1.0 if status == "success" else 0.0

    def _coverage_delta(self, result: Dict[str, Any]) -> float:
        if "coverage_delta" in result:
            return max(0.0, min(float(result["coverage_delta"]), 1.0))
        artifacts = result.get("artifacts", [])
        return min(len(artifacts) / EXPECTED_ARTIFACT_COUNT, 1.0) if artifacts else 0.0

    def _stability(self, result: Dict[str, Any], violations: Any) -> float:
        if "stability" in result:
            return max(0.0, min(float(result["stability"]), 1.0))
        if result.get("exception") or violations:
            return 0.0
        status = result.get("status") or result.get("execution_result")
        return 1.0 if status == "success" else 0.0
