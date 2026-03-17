"""vector_store_adapter — uniform async API over Qdrant vector store.

Wraps the Qdrant client behind a simple interface so callers never need
to import Qdrant-specific types.  Falls back to an in-memory list store
when Qdrant is unavailable.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

_FALLBACK_MAX = 50_000   # max entries in memory fallback


class VectorStoreAdapter:
    """Add / search vectors over Qdrant with graceful in-memory fallback.

    Parameters
    ----------
    url:
        Qdrant gRPC/HTTP URL, e.g. ``http://localhost:6333``.
    collection:
        Qdrant collection name.
    dim:
        Vector dimensionality (must match the embedding model output).
    """

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection: str = "aae_memory",
        dim: int = 384,
    ) -> None:
        self._url = url
        self._collection = collection
        self._dim = dim
        self._client: Any = None
        # fallback: list of (vector, payload, id)
        self._mem: List[Tuple[List[float], Dict[str, Any], str]] = []

    async def connect(self) -> None:
        """Open Qdrant client and ensure the collection exists."""
        try:
            from qdrant_client import AsyncQdrantClient  # type: ignore[import]
            from qdrant_client.models import (  # type: ignore[import]
                Distance,
                VectorParams,
            )

            self._client = AsyncQdrantClient(url=self._url)
            collections = await self._client.get_collections()
            names = [c.name for c in collections.collections]
            if self._collection not in names:
                await self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=self._dim, distance=Distance.COSINE
                    ),
                )
            log.info("VectorStoreAdapter connected (collection=%s)", self._collection)
        except Exception as exc:
            log.warning("Qdrant unavailable (%s); using fallback", exc)
            self._client = None

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    # ── write ─────────────────────────────────────────────────────────────────

    async def upsert(
        self,
        vector: List[float],
        payload: Dict[str, Any],
        point_id: Optional[str] = None,
    ) -> str:
        """Store a vector+payload, return the point ID."""
        pid = point_id or str(uuid.uuid4())
        if self._client:
            from qdrant_client.models import PointStruct  # type: ignore[import]
            await self._client.upsert(
                collection_name=self._collection,
                points=[PointStruct(id=pid, vector=vector, payload=payload)],
            )
        else:
            self._mem.append((vector, payload, pid))
            if len(self._mem) > _FALLBACK_MAX:
                self._mem = self._mem[-_FALLBACK_MAX:]
        return pid

    async def upsert_batch(
        self,
        records: List[Tuple[List[float], Dict[str, Any]]],
    ) -> List[str]:
        """Batch upsert; returns list of point IDs."""
        ids: List[str] = []
        if self._client:
            from qdrant_client.models import PointStruct  # type: ignore[import]
            points = []
            for vec, payload in records:
                pid = str(uuid.uuid4())
                ids.append(pid)
                points.append(
                    PointStruct(id=pid, vector=vec, payload=payload)
                )
            await self._client.upsert(
                collection_name=self._collection, points=points
            )
        else:
            for vec, payload in records:
                pid = await self.upsert(vec, payload)
                ids.append(pid)
        return ids

    # ── search ────────────────────────────────────────────────────────────────

    async def search(
        self,
        query_vector: List[float],
        k: int = 10,
        filter_payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return top-k results as list of ``{id, score, payload}`` dicts."""
        if self._client:
            from qdrant_client.models import Filter, FieldCondition, MatchValue  # type: ignore[import]
            qdrant_filter = None
            if filter_payload:
                conditions = [
                    FieldCondition(
                        key=k2, match=MatchValue(value=v)
                    )
                    for k2, v in filter_payload.items()
                ]
                qdrant_filter = Filter(must=conditions)
            hits = await self._client.search(
                collection_name=self._collection,
                query_vector=query_vector,
                limit=k,
                query_filter=qdrant_filter,
            )
            return [
                {"id": h.id, "score": h.score, "payload": h.payload}
                for h in hits
            ]
        # Fallback: cosine similarity brute-force
        return self._fallback_search(query_vector, k)

    # ── delete ────────────────────────────────────────────────────────────────

    async def delete(self, point_id: str) -> None:
        if self._client:
            from qdrant_client.models import PointIdsList  # type: ignore[import]
            await self._client.delete(
                collection_name=self._collection,
                points_selector=PointIdsList(points=[point_id]),
            )
        else:
            self._mem = [(v, p, i) for v, p, i in self._mem if i != point_id]

    async def count(self) -> int:
        if self._client:
            result = await self._client.count(self._collection)
            return result.count
        return len(self._mem)

    # ── internal ──────────────────────────────────────────────────────────────

    def _fallback_search(
        self, query: List[float], k: int
    ) -> List[Dict[str, Any]]:
        import math

        def cosine(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            return dot / (na * nb + 1e-9)

        scored = [
            (cosine(query, vec), payload, pid)
            for vec, payload, pid in self._mem
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"id": pid, "score": score, "payload": payload}
            for score, payload, pid in scored[:k]
        ]
