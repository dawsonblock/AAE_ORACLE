from __future__ import annotations

from typing import Any, Dict, List

from aae.contracts.planner import PlanBranch


class StateBuilder:
    """Constructs the rich planning state from raw context and task data.

    The state is consumed by BeamSearch, RolloutSimulator, and ultimately
    the LLM-backed PlanEvaluator.  It must include every signal available
    to the planner so that plan scoring is deterministic given the same
    inputs.
    """

    def build(
        self,
        goal: str,
        repo_context: Dict[str, Any] | None = None,
        localization_result: Dict[str, Any] | None = None,
        memory_context: Dict[str, Any] | None = None,
        task_metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Assemble a complete planning state dict.

        Args:
            goal: Human-readable engineering objective.
            repo_context: Graph / symbol context from the RIS.
            localization_result: Output of LocalizationService.localize().
            memory_context: Relevant episodic / vector memory entries.
            task_metadata: Arbitrary caller metadata (issue URL, repo path…).

        Returns:
            A flat, JSON-serialisable planning state.
        """
        state: Dict[str, Any] = {
            "goal": goal,
            "repo_context": repo_context or {},
            "localization": localization_result or {},
            "memory": memory_context or {},
            "metadata": task_metadata or {},
        }

        # Derive convenience signals for the planner
        state["suspected_files"] = self._extract_files(localization_result)
        state["suspected_functions"] = self._extract_functions(localization_result)
        state["failing_tests"] = self._extract_tests(localization_result)
        state["symbol_count"] = self._symbol_count(repo_context)
        state["call_depth"] = self._call_depth(repo_context)

        return state

    # ── extraction helpers ────────────────────────────────────────────────────

    def _extract_files(self, loc: Dict[str, Any] | None) -> List[str]:
        if not loc:
            return []
        files = loc.get("files", [])
        return [f.get("file_path", "") if isinstance(f, dict) else str(f)
                for f in files[:5]]

    def _extract_functions(self, loc: Dict[str, Any] | None) -> List[str]:
        if not loc:
            return []
        funcs = loc.get("functions", [])
        return [f.get("function_name", "") if isinstance(f, dict) else str(f)
                for f in funcs[:8]]

    def _extract_tests(self, loc: Dict[str, Any] | None) -> List[str]:
        if not loc:
            return []
        failures = loc.get("failures", [])
        return [str(f.get("test_id", "")) for f in failures if isinstance(f, dict)]

    def _symbol_count(self, ctx: Dict[str, Any] | None) -> int:
        if not ctx:
            return 0
        return int(ctx.get("symbol_count", ctx.get("node_count", 0)))

    def _call_depth(self, ctx: Dict[str, Any] | None) -> int:
        if not ctx:
            return 0
        return int(ctx.get("max_call_depth", 3))

    # ── branch helpers ────────────────────────────────────────────────────────

    def annotate_branch(
        self, branch: PlanBranch, state: Dict[str, Any]
    ) -> PlanBranch:
        """Attach state-derived metadata to a PlanBranch."""
        branch.metadata.setdefault("state_goal", state.get("goal", ""))
        branch.metadata.setdefault("suspected_files", state.get("suspected_files", []))
        return branch
