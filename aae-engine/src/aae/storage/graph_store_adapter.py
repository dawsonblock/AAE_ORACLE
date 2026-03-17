"""graph_store_adapter — adapts the AAE graph layer for the storage subsystem.

Provides a thin async wrapper so the storage subsystem can read/write the
graph store without hard-coding Neo4j or NetworkX imports.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class GraphStoreAdapter:
    """Async adapter over the AAE graph store (Neo4j or NetworkX).

    Parameters
    ----------
    backend:
        ``"networkx"`` (default, always available) or ``"neo4j"``.
    neo4j_uri:
        URI for Neo4j Bolt connection (only used when backend="neo4j").
    neo4j_auth:
        ``(user, password)`` tuple for Neo4j.
    """

    def __init__(
        self,
        backend: str = "networkx",
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_auth: tuple[str, str] = ("neo4j", "password"),
    ) -> None:
        self._backend = backend
        self._neo4j_uri = neo4j_uri
        self._neo4j_auth = neo4j_auth
        self._driver: Any = None
        self._graph: Any = None  # networkx DiGraph

    async def connect(self) -> None:
        if self._backend == "neo4j":
            await self._connect_neo4j()
        else:
            self._connect_networkx()

    async def close(self) -> None:
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass

    def available(self) -> bool:
        return self._driver is not None or self._graph is not None

    # ── node ops ──────────────────────────────────────────────────────────────

    async def add_node(
        self,
        node_id: str,
        label: str,
        properties: Dict[str, Any],
    ) -> None:
        if self._graph is not None:
            self._graph.add_node(
                node_id, label=label, **properties
            )
        elif self._driver:
            await self._neo4j_write(
                f"MERGE (n:{label} {{id: $id}}) SET n += $props",
                {"id": node_id, "props": properties},
            )

    async def get_node(
        self, node_id: str
    ) -> Optional[Dict[str, Any]]:
        if self._graph is not None:
            data = self._graph.nodes.get(node_id)
            return dict(data) if data else None
        if self._driver:
            rows = await self._neo4j_read(
                "MATCH (n {id: $id}) RETURN properties(n) AS p LIMIT 1",
                {"id": node_id},
            )
            return rows[0]["p"] if rows else None
        return None

    async def delete_node(self, node_id: str) -> None:
        if self._graph is not None:
            self._graph.remove_node(node_id)
        elif self._driver:
            await self._neo4j_write(
                "MATCH (n {id: $id}) DETACH DELETE n", {"id": node_id}
            )

    # ── edge ops ──────────────────────────────────────────────────────────────

    async def add_edge(
        self,
        src: str,
        dst: str,
        rel: str = "CALLS",
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        props = properties or {}
        if self._graph is not None:
            self._graph.add_edge(src, dst, rel=rel, **props)
        elif self._driver:
            await self._neo4j_write(
                f"MATCH (a {{id: $src}}), (b {{id: $dst}}) "
                f"MERGE (a)-[r:{rel}]->(b) SET r += $props",
                {"src": src, "dst": dst, "props": props},
            )

    async def get_neighbours(
        self,
        node_id: str,
        direction: str = "out",
    ) -> List[str]:
        if self._graph is not None:
            if direction == "out":
                return list(self._graph.successors(node_id))
            return list(self._graph.predecessors(node_id))
        if self._driver:
            if direction == "out":
                cypher = (
                    "MATCH (n {id: $id})-[]->(m) RETURN m.id AS id"
                )
            else:
                cypher = (
                    "MATCH (n {id: $id})<-[]-(m) RETURN m.id AS id"
                )
            rows = await self._neo4j_read(cypher, {"id": node_id})
            return [r["id"] for r in rows]
        return []

    # ── query ─────────────────────────────────────────────────────────────────

    async def query(self, cypher: str, params: Dict[str, Any]) -> List[Any]:
        if self._driver:
            return await self._neo4j_read(cypher, params)
        return []

    # ── internal ──────────────────────────────────────────────────────────────

    def _connect_networkx(self) -> None:
        try:
            import networkx as nx  # type: ignore[import]
            self._graph = nx.DiGraph()
            log.info("GraphStoreAdapter using NetworkX backend")
        except ImportError:
            log.warning("networkx not installed; graph store disabled")

    async def _connect_neo4j(self) -> None:
        try:
            from neo4j import AsyncGraphDatabase  # type: ignore[import]
            self._driver = AsyncGraphDatabase.driver(
                self._neo4j_uri, auth=self._neo4j_auth
            )
            log.info("GraphStoreAdapter connected to Neo4j")
        except Exception as exc:
            log.warning("Neo4j unavailable (%s); fallback to NetworkX", exc)
            self._connect_networkx()

    async def _neo4j_write(
        self, cypher: str, params: Dict[str, Any]
    ) -> None:
        async with self._driver.session() as sess:
            await sess.run(cypher, params)

    async def _neo4j_read(
        self, cypher: str, params: Dict[str, Any]
    ) -> List[Any]:
        async with self._driver.session() as sess:
            result = await sess.run(cypher, params)
            return [dict(r) async for r in result]
