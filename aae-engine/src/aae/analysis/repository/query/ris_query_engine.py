"""repository_intelligence/query/ris_query_engine — query the RIS indexes."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result of a RIS query."""

    query: str
    hits: List[Dict[str, Any]] = field(default_factory=list)
    total: int = 0
    source: str = "full_text"   # "full_text" | "vector" | "graph"

    def __len__(self) -> int:
        return len(self.hits)

    def __iter__(self):
        return iter(self.hits)

    def top(self, n: int = 5) -> List[Dict]:
        return self.hits[:n]


class RISQueryEngine:
    """Unified query interface over full-text and vector indexes.

    Parameters
    ----------
    ft_indexer:
        A :class:`FullTextIndexer` instance.
    vec_indexer:
        A :class:`VectorIndexer` instance (optional).
    graph:
        A :class:`RepoGraph` instance (optional).
    embed_fn:
        Callable(text) -> List[float] for vectorising queries.
    """

    def __init__(
        self,
        ft_indexer=None,
        vec_indexer=None,
        graph=None,
        embed_fn=None,
        # convenience alias used in tests / scripts
        full_text_indexer=None,
    ) -> None:
        self._ft = full_text_indexer or ft_indexer
        self._vec = vec_indexer
        self._graph = graph
        self._embed = embed_fn

    async def search_text(self, query: str, top_k: int = 10) -> QueryResult:
        """Full-text search using the inverted index."""
        if self._ft is None:
            return QueryResult(query=query, source="full_text")
        raw = self._ft.search(query, top_k=top_k)
        hits = []
        for item in raw:
            # Support both SearchResult objects and raw (doc_id, score) tuples
            if hasattr(item, "doc_id"):
                doc_id, score = item.doc_id, item.score
                file_ = getattr(item, "file", "")
                snippet = getattr(item, "snippet", "")
            else:
                doc_id, score = item[0], item[1]
                doc = self._ft.get_doc(doc_id) if hasattr(
                    self._ft, "get_doc"
                ) else None
                file_ = doc.file if doc else ""
                snippet = doc.content[:200] if doc else ""
            hits.append({
                "doc_id": doc_id,
                "score": round(score, 4),
                "file": file_,
                "snippet": snippet,
            })
        return QueryResult(
            query=query, hits=hits, total=len(hits), source="full_text"
        )

    def search_vector(
        self, query: str, top_k: int = 10
    ) -> QueryResult:
        """Semantic search using the vector index."""
        if self._vec is None or self._embed is None:
            return QueryResult(query=query, source="vector")
        try:
            emb = self._embed(query)
            raw = self._vec.search(emb, top_k=top_k)
        except Exception as exc:
            log.warning("Vector search failed: %s", exc)
            return QueryResult(query=query, source="vector")
        hits = [{"doc_id": doc_id, "score": round(score, 4)} for doc_id, score in raw]
        return QueryResult(query=query, hits=hits, total=len(hits), source="vector")

    def search_graph(
        self, symbol: str, depth: int = 2
    ) -> QueryResult:
        """Graph-neighbourhood search starting from *symbol*."""
        if self._graph is None:
            return QueryResult(query=symbol, source="graph")
        hits = []
        # Find node by label
        start = next(
            (nid for nid, n in self._graph.nodes.items() if n.label == symbol),
            None,
        )
        if start:
            visited = {start}
            frontier = [start]
            for _ in range(depth):
                next_frontier = []
                for nid in frontier:
                    for nbr in self._graph.neighbours(nid):
                        if nbr not in visited:
                            visited.add(nbr)
                            next_frontier.append(nbr)
                            node = self._graph.nodes.get(nbr)
                            if node:
                                hits.append(
                                    {
                                        "doc_id": nbr,
                                        "label": node.label,
                                        "kind": node.kind,
                                        "file": node.file,
                                    }
                                )
                frontier = next_frontier
        return QueryResult(
            query=symbol, hits=hits, total=len(hits), source="graph"
        )

    async def hybrid_search(
        self, query: str, top_k: int = 10
    ) -> QueryResult:
        """Merge full-text and vector results via reciprocal rank fusion."""
        ft_result = await self.search_text(query, top_k=top_k)
        vec_result = self.search_vector(query, top_k=top_k)
        rrf_scores: Dict[str, float] = {}
        for rank, hit in enumerate(ft_result.hits):
            rrf_scores[hit["doc_id"]] = rrf_scores.get(hit["doc_id"], 0) + 1 / (60 + rank)
        for rank, hit in enumerate(vec_result.hits):
            rrf_scores[hit["doc_id"]] = rrf_scores.get(hit["doc_id"], 0) + 1 / (60 + rank)
        merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        hits = [{"doc_id": d, "score": round(s, 6)} for d, s in merged[:top_k]]
        return QueryResult(query=query, hits=hits, total=len(hits), source="hybrid")
