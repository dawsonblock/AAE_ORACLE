from __future__ import annotations

from typing import Any, Dict, List

from aae.contracts.planner import PlanBranch
from aae.planner.plan_evaluator import PlanEvaluator
from aae.planner.rollout_simulator import RolloutSimulator


class BranchSimulator:
    """Simulates the execution of plan branches before committing to them.

    Each candidate PlanBranch is evaluated against a lightweight model of
    the repository state (affected functions, test suite, dependency graph)
    to produce a predicted outcome without actually running code.  This
    allows the planner to discard obviously bad branches cheaply.

    The simulator operates in three stages:
        1. Impact analysis  — which symbols change?
        2. Risk scoring     — how likely is a regression?
        3. Outcome estimate — predicted test pass rate after applying branch.
    """

    RISK_THRESHOLDS = {
        "low": 0.2,
        "medium": 0.5,
        "high": 0.8,
    }

    def __init__(
        self,
        evaluator: PlanEvaluator | None = None,
        rollout: RolloutSimulator | None = None,
    ) -> None:
        self.evaluator = evaluator or PlanEvaluator()
        self.rollout = rollout or RolloutSimulator()

    def simulate(
        self,
        branch: PlanBranch,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run a full pre-execution simulation for a single branch.

        Returns a simulation report with the following fields:
            affected_functions  — list of function names impacted by actions.
            dependency_ripple   — estimated downstream impact count.
            risk_score          — float 0–1 (higher = riskier).
            risk_level          — "low" | "medium" | "high".
            predicted_pass_rate — float 0–1.
            safe_to_execute     — bool shortcut.
        """
        affected = self._affected_functions(branch, state)
        ripple = self._dependency_ripple(affected, state)
        risk = self._compute_risk(branch, affected, ripple, state)
        pass_rate = self._predict_pass_rate(branch, risk, state)

        level = "low"
        for lvl, threshold in self.RISK_THRESHOLDS.items():
            if risk >= threshold:
                level = lvl

        return {
            "branch_id": branch.branch_id,
            "affected_functions": affected,
            "dependency_ripple": ripple,
            "risk_score": round(risk, 4),
            "risk_level": level,
            "predicted_pass_rate": round(pass_rate, 4),
            "safe_to_execute": risk < self.RISK_THRESHOLDS["high"],
        }

    def simulate_many(
        self,
        branches: List[PlanBranch],
        state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Simulate all branches and return sorted by predicted pass rate."""
        reports = [self.simulate(b, state) for b in branches]
        reports.sort(key=lambda r: r["predicted_pass_rate"], reverse=True)
        return reports

    # ── internal ─────────────────────────────────────────────────────────────

    def _affected_functions(
        self, branch: PlanBranch, state: Dict[str, Any]
    ) -> List[str]:
        """Extract function names targeted by branch actions."""
        affected: List[str] = []
        for action in branch.actions:
            if isinstance(action, dict):
                fn = action.get("function") or action.get("target_function")
                if fn:
                    affected.append(str(fn))
        # Append from localization if branch has no explicit targets
        if not affected:
            affected = state.get("suspected_functions", [])[:4]
        return affected

    def _dependency_ripple(
        self, affected: List[str], state: Dict[str, Any]
    ) -> int:
        """Estimate downstream caller count (simple heuristic)."""
        call_depth = int(state.get("call_depth", 2))
        return len(affected) * max(1, call_depth)

    def _compute_risk(
        self,
        branch: PlanBranch,
        affected: List[str],
        ripple: int,
        state: Dict[str, Any],
    ) -> float:
        symbol_count = max(1, int(state.get("symbol_count", 1000)))
        coverage_ratio = min(1.0, ripple / symbol_count)
        action_penalty = min(0.3, len(branch.actions) * 0.04)
        base = self.rollout.score(branch)
        risk = (1.0 - base) * 0.5 + coverage_ratio * 0.3 + action_penalty
        return min(1.0, max(0.0, risk))

    def _predict_pass_rate(
        self, branch: PlanBranch, risk: float, state: Dict[str, Any]
    ) -> float:
        evaluator_score = self.evaluator.score(branch)
        return max(0.0, min(1.0, evaluator_score * (1.0 - risk * 0.5)))
