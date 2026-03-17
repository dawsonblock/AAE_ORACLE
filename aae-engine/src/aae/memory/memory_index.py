"""memory_index — lightweight inverted index over in-memory entries.

Provides fast keyword and prefix searches over a flat dict-like store
without requiring a vector database.  Used as a fallback when Qdrant is
unavailable and as a first-pass filter before semantic re-ranking.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


class MemoryIndex:
    """Inverted token index over a ``{key: text}`` store.

    Usage::

        idx = MemoryIndex()
        idx.add("chunk:1", "async def fetch(url)...")
        results = idx.search("async fetch", k=5)

    Supports:
    - Token-level BM25-inspired scoring (simplified TF weighting)
    - Prefix lookup: ``idx.prefix("chunk:")``
    - Tag filtering: entries stored with ``tags`` can be filtered
    """

    _TOKEN_RE = re.compile(r"[a-z0-9_]+")
    _MIN_TOKEN_LEN = 2

    def __init__(self) -> None:
        # key → original text
        self._docs: Dict[str, str] = {}
        # key → tags
        self._tags: Dict[str, List[str]] = {}
        # token → set of keys containing it
        self._inverted: Dict[str, set[str]] = defaultdict(set)
        # token → per-key term frequency
        self._tf: Dict[str, Dict[str, int]] = defaultdict(dict)

    # ── write ─────────────────────────────────────────────────────────────────

    def add(
        self,
        key: str,
        text: str,
        tags: List[str] | None = None,
        overwrite: bool = True,
    ) -> None:
        """Index *key* with *text*."""
        if key in self._docs and not overwrite:
            return
        self._remove(key)
        self._docs[key] = text
        self._tags[key] = tags or []
        for token in self._tokenise(text):
            self._inverted[token].add(key)
            self._tf[token][key] = self._tf[token].get(key, 0) + 1

    def add_many(
        self,
        entries: List[Tuple[str, str]],
        tags: List[str] | None = None,
    ) -> None:
        for key, text in entries:
            self.add(key, text, tags=tags)

    def remove(self, key: str) -> bool:
        if key not in self._docs:
            return False
        self._remove(key)
        return True

    # ── search ────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        k: int = 10,
        tag_filter: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return top-*k* entries matching *query* tokens, best-first.

        Each result is ``{"key": str, "text": str, "score": float}``.
        """
        tokens = self._tokenise(query)
        if not tokens:
            return []

        # Accumulate scores: TF sum per document
        scores: Dict[str, float] = defaultdict(float)
        for token in tokens:
            for key in self._inverted.get(token, set()):
                scores[key] += float(self._tf[token].get(key, 0))

        # Tag filter
        if tag_filter:
            tag_set = set(tag_filter)
            scores = {
                k: v
                for k, v in scores.items()
                if tag_set.intersection(self._tags.get(k, []))
            }

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            {"key": k, "text": self._docs[k], "score": s}
            for k, s in ranked[:k]
            if k in self._docs
        ]

    def prefix(self, prefix: str) -> List[str]:
        """Return all keys starting with *prefix*."""
        return [k for k in self._docs if k.startswith(prefix)]

    # ── introspection ─────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._docs)

    def __contains__(self, key: object) -> bool:
        return str(key) in self._docs

    def keys(self) -> List[str]:
        return list(self._docs.keys())

    def get(self, key: str) -> Optional[str]:
        return self._docs.get(key)

    # ── internal ──────────────────────────────────────────────────────────────

    def _tokenise(self, text: str) -> List[str]:
        return [
            t
            for t in self._TOKEN_RE.findall(text.lower())
            if len(t) >= self._MIN_TOKEN_LEN
        ]

    def _remove(self, key: str) -> None:
        text = self._docs.pop(key, "")
        self._tags.pop(key, None)
        for token in self._tokenise(text):
            self._inverted[token].discard(key)
            self._tf[token].pop(key, None)
            if not self._inverted[token]:
                del self._inverted[token]
