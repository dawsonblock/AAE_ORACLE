from __future__ import annotations

from typing import Any, Dict, List


class AgentContextBuilder:
    """Constructs focused context windows for LLM-backed agents.

    Agents cannot consume raw repositories.  This builder assembles a
    compact, token-bounded context from multiple sources so that the agent
    receives exactly the information it needs to act — no more, no less.

    Build pipeline::

        issue text
            ↓ symbol search (RIS)
            ↓ call graph expansion
            ↓ test coverage
            ↓ semantic search
            ↓ memory injection
            ↓ trimmed context dict
    """

    DEFAULT_MAX_TOKENS = 8000
    DEFAULT_MAX_FILES = 5
    DEFAULT_MAX_FUNCTIONS = 10

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_files: int = DEFAULT_MAX_FILES,
        max_functions: int = DEFAULT_MAX_FUNCTIONS,
    ) -> None:
        self.max_tokens = max_tokens
        self.max_files = max_files
        self.max_functions = max_functions

    def build(
        self,
        goal: str,
        localization: Dict[str, Any] | None = None,
        repo_graph: Dict[str, Any] | None = None,
        memory_entries: List[Dict[str, Any]] | None = None,
        extra: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Assemble an agent context dict from heterogeneous sources.

        Returns a dict safe to serialise and pass to any agent's ``run``
        method as the ``context`` argument.
        """
        ctx: Dict[str, Any] = {
            "goal": goal,
            "suspected_files": [],
            "suspected_functions": [],
            "failing_tests": [],
            "relevant_code": [],
            "memory": [],
        }

        if localization:
            ctx["suspected_files"] = self._top_files(localization)
            ctx["suspected_functions"] = self._top_functions(localization)
            ctx["failing_tests"] = self._failing_tests(localization)

        if repo_graph:
            ctx["relevant_code"] = self._relevant_snippets(
                ctx["suspected_functions"], repo_graph
            )
            ctx["call_chains"] = self._call_chains(
                ctx["suspected_functions"], repo_graph
            )

        if memory_entries:
            ctx["memory"] = self._trim_memory(memory_entries)

        if extra:
            ctx.update(extra)

        return self._trim(ctx)

    # ── extraction ────────────────────────────────────────────────────────────

    def _top_files(self, loc: Dict[str, Any]) -> List[str]:
        files = loc.get("files", [])
        return [
            f["file_path"] if isinstance(f, dict) else str(f)
            for f in files[: self.max_files]
        ]

    def _top_functions(self, loc: Dict[str, Any]) -> List[str]:
        funcs = loc.get("functions", [])
        return [
            f["function_name"] if isinstance(f, dict) else str(f)
            for f in funcs[: self.max_functions]
        ]

    def _failing_tests(self, loc: Dict[str, Any]) -> List[str]:
        failures = loc.get("failures", [])
        return [str(f.get("test_id", "")) for f in failures if isinstance(f, dict)]

    def _relevant_snippets(
        self, function_names: List[str], graph: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        snippets = []
        for name in function_names:
            snippet = graph.get("snippets", {}).get(name)
            if snippet:
                snippets.append({"name": name, "source": str(snippet)[:500]})
        return snippets

    def _call_chains(
        self, function_names: List[str], graph: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        chains = []
        raw = graph.get("call_chains", {})
        for name in function_names:
            chain = raw.get(name, [])
            if chain:
                chains.append({"root": name, "chain": chain[:5]})
        return chains

    def _trim_memory(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return entries[:10]

    def _trim(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Enforce approximate token budget by truncating long lists."""
        if len(str(ctx)) > self.max_tokens * 4:   # rough char estimate
            ctx["relevant_code"] = ctx.get("relevant_code", [])[:3]
            ctx["memory"] = ctx.get("memory", [])[:5]
        return ctx
