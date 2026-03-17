"""repository_intelligence/indexing/vector_indexer — vector similarity index."""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """A document with a dense embedding vector."""

    doc_id: str
    content: str
    embedding: List[float] = field(default_factory=list)
    file: str = ""
    metadata: Dict = field(default_factory=dict)


class VectorIndexer:
    """In-memory cosine-similarity vector index.

    For production, delegates to a Qdrant backend when available.
    """

    def __init__(self, qdrant_client=None, collection: str = "ris") -> None:
        self._qdrant = qdrant_client
        self._collection = collection
        self._docs: Dict[str, VectorDocument] = {}

    def add(self, doc: VectorDocument) -> None:
        self._docs[doc.doc_id] = doc
        if self._qdrant and doc.embedding:
            self._upsert_qdrant(doc)

    def add_many(self, docs: List[VectorDocument]) -> None:
        for doc in docs:
            self.add(doc)

    def search(
        self, query_embedding: List[float], top_k: int = 10
    ) -> List[Tuple[str, float]]:
        if self._qdrant:
            return self._search_qdrant(query_embedding, top_k)
        return self._cosine_search(query_embedding, top_k)

    def get(self, doc_id: str) -> Optional[VectorDocument]:
        return self._docs.get(doc_id)

    # ── internals ─────────────────────────────────────────────────────────────

    def _cosine_search(
        self, query: List[float], top_k: int
    ) -> List[Tuple[str, float]]:
        try:
            import numpy as np
            q = np.array(query, dtype=float)
            qn = np.linalg.norm(q)
            if qn == 0:
                return []
            results = []
            for doc in self._docs.values():
                if not doc.embedding:
                    continue
                v = np.array(doc.embedding, dtype=float)
                vn = np.linalg.norm(v)
                if vn == 0:
                    continue
                sim = float(np.dot(q, v) / (qn * vn))
                results.append((doc.doc_id, sim))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        except ImportError:
            log.warning("numpy not available for cosine search")
            return []

    def _upsert_qdrant(self, doc: VectorDocument) -> None:
        try:
            from qdrant_client.models import PointStruct
            # Use a stable, deterministic hash (Python's hash() is salted)
            stable_id = int(
                hashlib.md5(doc.doc_id.encode()).hexdigest(), 16
            ) & 0xFFFF_FFFF
            self._qdrant.upsert(
                collection_name=self._collection,
                points=[
                    PointStruct(
                        id=stable_id,
                        vector=doc.embedding,
                        payload={"doc_id": doc.doc_id, "file": doc.file},
                    )
                ],
            )
        except Exception as exc:
            log.debug("Qdrant upsert failed: %s", exc)

    def _search_qdrant(
        self, query: List[float], top_k: int
    ) -> List[Tuple[str, float]]:
        try:
            hits = self._qdrant.search(
                collection_name=self._collection,
                query_vector=query,
                limit=top_k,
            )
            return [
                (h.payload.get("doc_id", str(h.id)), h.score) for h in hits
            ]
        except Exception as exc:
            log.debug("Qdrant search failed: %s; falling back", exc)
            return self._cosine_search(query, top_k)
