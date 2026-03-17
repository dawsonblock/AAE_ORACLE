"""repository_intelligence/indexing/full_text_indexer — BM25-style index."""
from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result from the full-text index."""

    doc_id: str
    score: float
    file: str = ""
    snippet: str = ""


@dataclass
class IndexDocument:
    """A document stored in the full-text index."""

    doc_id: str
    content: str
    file: str = ""
    language: str = ""
    tokens: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.tokens:
            self.tokens = _tokenize(self.content)


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z_]\w*", text.lower())


class FullTextIndexer:
    """Simple inverted-index full-text search over repository files.

    Uses a TF-IDF-inspired scoring function.
    """

    def __init__(self) -> None:
        self._docs: Dict[str, IndexDocument] = {}
        self._index: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
        self._df: Dict[str, int] = defaultdict(int)

    def add(self, doc: IndexDocument) -> None:
        if doc.doc_id in self._docs:
            # remove old posting lists before re-indexing
            self._remove(doc.doc_id)
        self._docs[doc.doc_id] = doc
        freq: Dict[str, int] = {}
        for tok in doc.tokens:
            freq[tok] = freq.get(tok, 0) + 1
        for tok, count in freq.items():
            self._index[tok].append((doc.doc_id, count))
            self._df[tok] += 1

    def _remove(self, doc_id: str) -> None:
        """Remove *doc_id* from the posting lists (for re-indexing)."""
        old = self._docs.pop(doc_id, None)
        if old is None:
            return
        for tok in set(old.tokens):
            self._index[tok] = [
                (d, c) for d, c in self._index[tok] if d != doc_id
            ]
            if self._index[tok]:
                self._df[tok] = max(0, self._df[tok] - 1)
            else:
                del self._index[tok]
                del self._df[tok]

    def index(
        self,
        doc_id: str,
        content: str,
        file: str = "",
        language: str = "",
    ) -> None:
        """Convenience wrapper: create an :class:`IndexDocument` and add it."""
        self.add(IndexDocument(
            doc_id=doc_id,
            content=content,
            file=file or doc_id,
            language=language,
        ))

    def add_many(self, docs: List[IndexDocument]) -> None:
        for doc in docs:
            self.add(doc)

    def search(
        self, query: str, top_k: int = 10
    ) -> List[SearchResult]:
        """Return ranked :class:`SearchResult` objects."""
        qtokens = _tokenize(query)
        N = len(self._docs)
        if N == 0 or not qtokens:
            return []
        scores: Dict[str, float] = defaultdict(float)
        for tok in qtokens:
            if tok not in self._index:
                continue
            idf = math.log((N + 1) / (self._df[tok] + 1)) + 1
            for doc_id, tf in self._index[tok]:
                doc = self._docs.get(doc_id)
                doc_len = len(doc.tokens) if doc else 1
                tf_norm = tf / (1 + 0.5 * doc_len / 100)
                scores[doc_id] += tf_norm * idf
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for doc_id, score in ranked[:top_k]:
            doc = self._docs.get(doc_id)
            results.append(SearchResult(
                doc_id=doc_id,
                score=round(score, 4),
                file=doc.file if doc else "",
                snippet=doc.content[:200] if doc else "",
            ))
        return results

    def search_raw(
        self, query: str, top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """Return raw ``(doc_id, score)`` tuples."""
        return [(r.doc_id, r.score) for r in self.search(query, top_k)]

    def get_doc(self, doc_id: str) -> Optional[IndexDocument]:
        return self._docs.get(doc_id)

    def stats(self) -> Dict:
        return {
            "documents": len(self._docs),
            "unique_tokens": len(self._index),
        }
