from __future__ import annotations

from typing import Any, Dict, List

from aae.contracts.planner import PlanBranch
from aae.planner.plan_evaluator import PlanEvaluator


class PolicyRouter:
    """Routes plan branches to the appropriate execution strategy.

    After the beam-search phase produces a shortlist of PlanBranches,
    the PolicyRouter decides *how* each branch should be executed:

        * ``direct``    — single-agent, fast path for simple tasks.
        * ``parallel``  — multiple agents work the branch concurrently.
        * ``iterative`` — multi-round repair loop (for patch + test cycles).
        * ``research``  — triggers a research sub-task first.
        * ``escalate``  — requires human review before proceeding.

    The decision logic is a simple rule-based policy that can be replaced
    by a learned model (see ``learning/tool_policy_model.py``) once
    enough trajectory data has been collected.
    """

    def __init__(self, evaluator: PlanEvaluator | None = None) -> None:
        self.evaluator = evaluator or PlanEvaluator()

    def route(self, branches: List[PlanBranch], state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Annotate each branch with an execution strategy.

        Returns a list of routing decisions, one per branch.
        """
        decisions = []
        for branch in branches:
            strategy = self._decide_strategy(branch, state)
            decisions.append({
                "branch_id": branch.branch_id,
                "strategy": strategy,
                "branch": branch,
                "priority": branch.score,
            })
        # Higher-scored branches execute first
        decisions.sort(key=lambda d: d["priority"], reverse=True)
        return decisions

    def select_best(
        self,
        branches: List[PlanBranch],
        state: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        """Return the single highest-priority routing decision."""
        decisions = self.route(branches, state)
        return decisions[0] if decisions else None

    # ── internal ──────────────────────────────────────────────────────────────

    def _decide_strategy(
        self, branch: PlanBranch, state: Dict[str, Any]
    ) -> str:
        goal = str(state.get("goal", "")).lower()
        actions = branch.actions

        # Security or unknown vulnerability → escalate to human
        if any(x in goal for x in ("cve", "exploit", "rce", "sqli")):
            return "escalate"

        # Deep research needed before acting
        if any(x in goal for x in ("research", "investigate", "understand")):
            if not state.get("memory", {}).get("research_complete"):
                return "research"

        # Multi-file patch → iterative repair loop
        suspected_files: List[str] = state.get("suspected_files", [])
        if len(suspected_files) > 3 or len(actions) > 6:
            return "iterative"

        # Parallelisable if actions are independent
        if self._actions_are_independent(actions):
            return "parallel"

        return "direct"

    def _actions_are_independent(self, actions: List[Any]) -> bool:
        """Heuristic: actions are independent if they target different files."""
        files = set()
        for action in actions:
            target = None
            if isinstance(action, dict):
                target = action.get("file") or action.get("target_file")
            elif hasattr(action, "file"):
                target = action.file
            if target:
                if target in files:
                    return False
                files.add(target)
        return len(files) > 1
