"""Experiment evaluator — real scoring of execution outcomes.

Replaces stub scoring with a multi-signal evaluation that considers
build success, test pass rate, safety, latency, and artifact presence.
"""
from __future__ import annotations

from typing import Any, Dict

# Scoring constants
EXPECTED_ARTIFACT_COUNT = 5.0
MAX_ACCEPTABLE_LATENCY_MS = 2000.0
NEUTRAL_TEST_SCORE = 0.5


class ExperimentEvaluator:
    """Score experiment outcomes using multiple evaluation signals."""

    def evaluate(self, goal: str, result: Dict[str, Any]) -> Dict[str, Any]:
        metrics: Dict[str, float] = {}

        # binary success
        metrics["success"] = 1.0 if result.get("status") == "success" else 0.0

        # execution stability — no exceptions
        metrics["no_exceptions"] = 1.0 if not result.get("exception") else 0.0

        # artifact presence (normalized to 0-1)
        artifacts = result.get("artifacts", [])
        metrics["artifact_count"] = min(len(artifacts) / EXPECTED_ARTIFACT_COUNT, 1.0) if artifacts else 0.0

        # latency penalty (lower is better, capped at MAX_ACCEPTABLE_LATENCY_MS)
        latency = result.get("latency_ms", 1000)
        metrics["latency_score"] = max(0.0, 1.0 - (latency / MAX_ACCEPTABLE_LATENCY_MS))

        # test pass rate
        test_passed = result.get("tests_passed", 0)
        test_total = result.get("tests_total", 0)
        if test_total > 0:
            metrics["test_pass_rate"] = test_passed / test_total
        else:
            metrics["test_pass_rate"] = NEUTRAL_TEST_SCORE

        # safety — no violations
        violations = result.get("safety_violations", [])
        metrics["safety_score"] = 1.0 if not violations else 0.0

        # aggregate score
        score = sum(metrics.values()) / len(metrics) if metrics else 0.0

        return {
            "score": round(score, 4),
            "metrics": metrics,
        }
