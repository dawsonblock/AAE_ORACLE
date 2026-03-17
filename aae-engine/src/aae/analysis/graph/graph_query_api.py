"""graph_query_api — lightweight REST-style API surface for the graph layer.

Wraps ``GraphQuery`` and ``SymbolTable`` behind async coroutines that can
be called by agents, planners, or gateway handlers without importing the
full graph subsystem.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class GraphQueryResult:
    """Generic result container for all graph API calls."""

    query: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    total: int = 0
    error: Optional[str] = None

    def ok(self) -> bool:
        return self.error is None


class GraphQueryAPI:
    """High-level async query surface over the graph layer.

    All methods return ``GraphQueryResult`` — callers never touch raw
    graph internals.

    Parameters
    ----------
    graph_query:
        An instance of ``src.aae.graph.graph_query.GraphQuery``.
    symbol_table:
        An instance of ``src.aae.graph.symbol_table.SymbolTable``.
    graph_store:
        An instance of ``src.aae.graph.graph_store.GraphStore``.
    """

    def __init__(
        self,
        graph_query: Any | None = None,
        symbol_table: Any | None = None,
        graph_store: Any | None = None,
    ) -> None:
        self._gq = graph_query
        self._st = symbol_table
        self._gs = graph_store

    # ── symbol lookup ─────────────────────────────────────────────────────────

    async def lookup_symbol(self, name: str) -> GraphQueryResult:
        """Return declaration info for a symbol by name."""
        res = GraphQueryResult(query=f"lookup:{name}")
        try:
            raw = self._st.get(name) if self._st else None
            if raw:
                res.results = [raw if isinstance(raw, dict) else {"raw": raw}]
                res.total = 1
            else:
                res.results = []
        except Exception as exc:
            res.error = str(exc)
            log.warning("lookup_symbol(%s) error: %s", name, exc)
        return res

    # ── call graph ────────────────────────────────────────────────────────────

    async def get_callers(self, symbol: str) -> GraphQueryResult:
        """Return all direct callers of *symbol*."""
        res = GraphQueryResult(query=f"callers:{symbol}")
        try:
            raw = self._gq.callers(symbol) if self._gq else []
            res.results = [{"name": s} for s in (raw or [])]
            res.total = len(res.results)
        except Exception as exc:
            res.error = str(exc)
            log.warning("get_callers(%s) error: %s", symbol, exc)
        return res

    async def get_callees(self, symbol: str) -> GraphQueryResult:
        """Return all direct callees of *symbol*."""
        res = GraphQueryResult(query=f"callees:{symbol}")
        try:
            raw = self._gq.callees(symbol) if self._gq else []
            res.results = [{"name": s} for s in (raw or [])]
            res.total = len(res.results)
        except Exception as exc:
            res.error = str(exc)
            log.warning("get_callees(%s) error: %s", symbol, exc)
        return res

    async def get_path(
        self, source: str, target: str, max_depth: int = 5
    ) -> GraphQueryResult:
        """Find a call path from *source* to *target*."""
        res = GraphQueryResult(query=f"path:{source}->{target}")
        try:
            if self._gq and hasattr(self._gq, "shortest_path"):
                path = self._gq.shortest_path(source, target, max_depth)
                res.results = [{"path": path}]
                res.total = len(path)
            else:
                res.results = []
        except Exception as exc:
            res.error = str(exc)
            log.warning("get_path(%s->%s) error: %s", source, target, exc)
        return res

    # ── dependencies ─────────────────────────────────────────────────────────

    async def get_dependencies(
        self, module: str, transitive: bool = False
    ) -> GraphQueryResult:
        """Return import dependencies for *module*."""
        res = GraphQueryResult(query=f"deps:{module}")
        try:
            if self._gs:
                raw = self._gs.get_module_deps(module, transitive=transitive)
                res.results = [{"module": d} for d in (raw or [])]
                res.total = len(res.results)
        except Exception as exc:
            res.error = str(exc)
            log.warning("get_dependencies(%s) error: %s", module, exc)
        return res

    async def get_dependents(self, module: str) -> GraphQueryResult:
        """Return modules that import *module*."""
        res = GraphQueryResult(query=f"rdeps:{module}")
        try:
            if self._gs:
                raw = self._gs.get_module_rdeps(module)
                res.results = [{"module": d} for d in (raw or [])]
                res.total = len(res.results)
        except Exception as exc:
            res.error = str(exc)
            log.warning("get_dependents(%s) error: %s", module, exc)
        return res

    # ── impact analysis ───────────────────────────────────────────────────────

    async def impact(
        self, symbol: str, depth: int = 3
    ) -> GraphQueryResult:
        """Return all symbols potentially impacted by changes to *symbol*.

        Uses reverse BFS over the call graph.
        """
        res = GraphQueryResult(query=f"impact:{symbol}(depth={depth})")
        try:
            visited: set[str] = set()
            frontier = [symbol]
            for _ in range(depth):
                next_frontier: List[str] = []
                for sym in frontier:
                    callers_res = await self.get_callers(sym)
                    for r in callers_res.results:
                        name = r.get("name", "")
                        if name and name not in visited:
                            visited.add(name)
                            next_frontier.append(name)
                frontier = next_frontier
            visited.discard(symbol)
            res.results = [{"symbol": s} for s in sorted(visited)]
            res.total = len(res.results)
        except Exception as exc:
            res.error = str(exc)
        return res

    # ── batch ─────────────────────────────────────────────────────────────────

    async def batch_lookup(self, names: List[str]) -> List[GraphQueryResult]:
        """Lookup multiple symbols; returns one result per name."""
        import asyncio

        coros = [self.lookup_symbol(n) for n in names]
        return list(await asyncio.gather(*coros))
