"""graph_context_builder — produces LLM-ready graph context slices.

Takes a list of focal symbols (functions, classes) and builds a compact
textual representation of the local graph neighbourhood: direct callers,
direct callees, data-flow edges, and inheritance chains.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_MAX_HOPS = 2
_MAX_NEIGHBOURS = 15


class GraphContextBuilder:
    """Translate graph data into a focused context dict for agent prompts.

    Parameters
    ----------
    graph_store:
        Any object exposing ``get_symbol(name)``, ``get_callers(name)``,
        ``get_callees(name)``, and ``get_dataflow(name)``.
    max_hops:
        BFS depth from each focal symbol.
    max_neighbours:
        Maximum total neighbours to include per symbol.
    """

    def __init__(
        self,
        graph_store: Any | None = None,
        max_hops: int = _MAX_HOPS,
        max_neighbours: int = _MAX_NEIGHBOURS,
    ) -> None:
        self._gs = graph_store
        self.max_hops = max_hops
        self.max_neighbours = max_neighbours

    def build(
        self,
        focal_symbols: List[str],
        include_dataflow: bool = False,
    ) -> Dict[str, Any]:
        """Return a context dict describing the subgraph around *focal_symbols*.

        Keys
        ----
        focal_symbols : list[str]
        call_graph    : {symbol: {callers: [], callees: []}}
        dataflow      : {symbol: {inputs: [], outputs: []}} (opt.)
        summary       : str  human-readable one-liner
        """
        ctx: Dict[str, Any] = {
            "focal_symbols": focal_symbols,
            "call_graph": {},
            "summary": "",
        }
        if include_dataflow:
            ctx["dataflow"] = {}

        if not self._gs:
            ctx["summary"] = "graph store unavailable"
            return ctx

        seen: set[str] = set()
        for sym in focal_symbols:
            self._bfs(sym, ctx, include_dataflow, seen)

        ctx["summary"] = (
            f"{len(ctx['call_graph'])} symbols in {len(focal_symbols)}"
            f"-focal neighbourhood (depth={self.max_hops})"
        )
        return ctx

    def build_inheritance_chain(self, class_name: str) -> List[str]:
        """Return MRO-style ancestor list for *class_name*."""
        if not self._gs:
            return []
        chain: List[str] = []
        visited: set[str] = set()
        current = class_name
        while current and current not in visited:
            visited.add(current)
            chain.append(current)
            info = self._safe_get(current)
            current = (info or {}).get("parent_class", "")
        return chain

    def summarise_path(
        self, source: str, target: str, path: List[str]
    ) -> str:
        """Return a human-readable description of *path*."""
        if not path:
            return f"No path found from {source} to {target}."
        hops = " → ".join(path)
        return f"Call path ({len(path)} hops): {hops}"

    # ── internal ──────────────────────────────────────────────────────────────

    def _bfs(
        self,
        root: str,
        ctx: Dict[str, Any],
        include_dataflow: bool,
        seen: set[str],
    ) -> None:
        queue = [(root, 0)]
        while queue:
            sym, depth = queue.pop(0)
            if sym in seen or depth > self.max_hops:
                continue
            seen.add(sym)
            info = self._safe_get(sym)
            if info is None:
                continue
            callers = self._safe_list(info.get("callers", []))
            callees = self._safe_list(info.get("callees", []))
            ctx["call_graph"][sym] = {
                "callers": callers[: self.max_neighbours],
                "callees": callees[: self.max_neighbours],
            }
            if include_dataflow:
                ctx["dataflow"][sym] = {
                    "inputs": self._safe_list(info.get("inputs", [])),
                    "outputs": self._safe_list(info.get("outputs", [])),
                }
            for neighbour in (callers + callees)[: self.max_neighbours]:
                if neighbour not in seen:
                    queue.append((neighbour, depth + 1))

    def _safe_get(self, name: str) -> Optional[Dict[str, Any]]:
        try:
            return self._gs.get_symbol(name)
        except Exception as exc:
            log.debug("graph_store.get_symbol(%s) failed: %s", name, exc)
            return None

    @staticmethod
    def _safe_list(val: Any) -> List[str]:
        if isinstance(val, list):
            return [str(v) for v in val]
        return []
