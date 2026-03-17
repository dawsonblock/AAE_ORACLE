"""artifact_store — content-addressed artefact store for the storage layer.

Sits above ``ArtifactWriter`` (which handles raw file I/O) and provides:
- Content-addressed storage (SHA-256 dedup)
- Metadata index in memory + optional Postgres persistence
- Tag-based retrieval
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ArtifactStore:
    """Content-addressed artefact store backed by the local filesystem.

    Parameters
    ----------
    root:
        Base directory for artefact blobs.  Sub-dirs are created lazily.
    postgres_store:
        Optional ``PostgresStore`` for durable metadata persistence.
    """

    def __init__(
        self,
        root: Path | str = ".artifacts/cas",
        postgres_store: Any | None = None,
    ) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._pg = postgres_store
        # In-memory metadata index: sha256 → metadata dict
        self._index: Dict[str, Dict[str, Any]] = {}

    # ── write ─────────────────────────────────────────────────────────────────

    async def write(
        self, name: str, content: bytes | str, **kwargs
    ) -> str:
        """Convenience alias for :meth:`store`. Returns SHA-256 key."""
        return await self.store(content, **kwargs)

    async def read(self, sha: str) -> Optional[bytes]:
        """Convenience alias for :meth:`load`. Returns raw bytes or None."""
        return self.load(sha)

    async def store(
        self,
        content: bytes | str,
        category: str = "generic",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Store *content* and return its SHA-256 key."""
        if isinstance(content, str):
            content = content.encode()
        sha = _sha256(content)
        blob_path = self._blob_path(sha)
        if not blob_path.exists():
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            blob_path.write_bytes(content)
            log.debug("artifact stored sha=%s", sha[:16])

        entry = {
            "sha": sha,
            "size": len(content),
            "category": category,
            "tags": tags or [],
            "stored_at": time.time(),
            **(metadata or {}),
        }
        self._index[sha] = entry

        if self._pg:
            await self._pg.kv_set(f"artifact:{sha}", entry)

        return sha

    async def store_json(
        self,
        data: Any,
        category: str = "generic",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await self.store(
            json.dumps(data, indent=2).encode(),
            category=category,
            tags=tags,
            metadata=metadata,
        )

    # ── read ──────────────────────────────────────────────────────────────────

    def load(self, sha: str) -> Optional[bytes]:
        """Load raw bytes for *sha*, or None if not found."""
        path = self._blob_path(sha)
        if path.exists():
            return path.read_bytes()
        return None

    def load_text(self, sha: str) -> Optional[str]:
        raw = self.load(sha)
        return raw.decode() if raw is not None else None

    def load_json(self, sha: str) -> Optional[Any]:
        raw = self.load(sha)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    # ── query ─────────────────────────────────────────────────────────────────

    def get_metadata(self, sha: str) -> Optional[Dict[str, Any]]:
        return self._index.get(sha)

    def list_by_category(self, category: str) -> List[str]:
        return [
            sha for sha, meta in self._index.items()
            if meta.get("category") == category
        ]

    def list_by_tag(self, tag: str) -> List[str]:
        return [
            sha for sha, meta in self._index.items()
            if tag in meta.get("tags", [])
        ]

    def exists(self, sha: str) -> bool:
        return self._blob_path(sha).exists()

    def size(self) -> int:
        return len(self._index)

    # ── internal ──────────────────────────────────────────────────────────────

    def _blob_path(self, sha: str) -> Path:
        # Two-level sharding: first 2 hex chars / rest
        return self._root / sha[:2] / sha[2:]
