"""working_memory — bounded in-process short-term memory for a single task.

Acts as a scratch-pad that agents populate while working on a task. Entries
expire when the task completes (or TTL elapses).  This sits at L0 in the
memory stack — faster than L1 in-memory store because it lives in the same
event loop with zero serialisation overhead.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Dict, Iterator, List, Optional


class WorkingMemoryEntry:
    """A single entry in working memory."""

    def __init__(self, key: str, value: Any, ttl: float = 300.0) -> None:
        self.key = key
        self.value = value
        self._expires_at = time.monotonic() + ttl

    def alive(self) -> bool:
        return time.monotonic() < self._expires_at

    def refresh(self, ttl: float = 300.0) -> None:
        self._expires_at = time.monotonic() + ttl


class WorkingMemory:
    """Bounded LRU working memory for a single planning task.

    Parameters
    ----------
    max_entries:
        Maximum number of live entries.  When the limit is reached the
        oldest entry is evicted (LRU semantics).
    default_ttl:
        Seconds until an entry expires if not refreshed.
    """

    def __init__(
        self,
        max_entries: int = 512,
        default_ttl: float = 300.0,
    ) -> None:
        self._max = max_entries
        self._ttl = default_ttl
        self._store: OrderedDict[str, WorkingMemoryEntry] = OrderedDict()

    # ── write ─────────────────────────────────────────────────────────────────

    def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Write *key* → *value* with optional per-entry *ttl*."""
        effective_ttl = ttl if ttl is not None else self._ttl
        if key in self._store:
            self._store.move_to_end(key)
            entry = self._store[key]
            entry.value = value
            entry.refresh(effective_ttl)
        else:
            self._evict_expired()
            if len(self._store) >= self._max:
                self._store.popitem(last=False)  # evict LRU
            self._store[key] = WorkingMemoryEntry(key, value, effective_ttl)

    def update(self, data: Dict[str, Any]) -> None:
        """Bulk put from dict."""
        for k, v in data.items():
            self.put(k, v)

    # ── read ──────────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key* or *default* if missing/expired."""
        entry = self._store.get(key)
        if entry is None:
            return default
        if not entry.alive():
            del self._store[key]
            return default
        self._store.move_to_end(key)
        return entry.value

    def get_all(self, prefix: str = "") -> Dict[str, Any]:
        """Return all live entries, optionally filtered by key *prefix*."""
        self._evict_expired()
        return {
            k: e.value
            for k, e in self._store.items()
            if k.startswith(prefix)
        }

    def keys(self) -> List[str]:
        self._evict_expired()
        return list(self._store.keys())

    # ── delete ────────────────────────────────────────────────────────────────

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        self._store.clear()

    # ── iteration ─────────────────────────────────────────────────────────────

    def __iter__(self) -> Iterator[str]:
        self._evict_expired()
        return iter(list(self._store.keys()))

    def __len__(self) -> int:
        self._evict_expired()
        return len(self._store)

    def __contains__(self, key: object) -> bool:
        entry = self._store.get(str(key))
        return entry is not None and entry.alive()

    # ── serialisation ─────────────────────────────────────────────────────────

    def snapshot(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of live entries."""
        self._evict_expired()
        return {k: e.value for k, e in self._store.items()}

    def restore(self, snapshot: Dict[str, Any]) -> None:
        """Restore from a previous snapshot (useful for checkpoint replay)."""
        for k, v in snapshot.items():
            self.put(k, v)

    # ── internal ──────────────────────────────────────────────────────────────

    def _evict_expired(self) -> None:
        dead = [k for k, e in self._store.items() if not e.alive()]
        for k in dead:
            del self._store[k]
