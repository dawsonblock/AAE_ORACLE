from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional



class EventStore:
    """Durable event store with optional PostgreSQL backend.

    Falls back to an in-memory list when the database is unavailable so
    the system can operate in single-node / test mode without infrastructure.
    """

    TABLE_DDL = """
    CREATE TABLE IF NOT EXISTS aae_events (
        id          TEXT        PRIMARY KEY,
        event_type  TEXT        NOT NULL,
        workflow_id TEXT,
        source      TEXT,
        payload     JSONB,
        created_at  DOUBLE PRECISION NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_aae_events_workflow
        ON aae_events (workflow_id);
    CREATE INDEX IF NOT EXISTS idx_aae_events_type
        ON aae_events (event_type);
    """

    def __init__(
        self,
        dsn: str | None = None,
        jsonl_path: str | None = None,
    ) -> None:
        self._dsn = dsn
        self._jsonl_path = Path(jsonl_path) if jsonl_path else None
        self._memory: List[Dict[str, Any]] = []
        self._db: Any = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def setup(self) -> None:
        """Create database tables if Postgres is configured."""
        if not self._dsn:
            return
        try:
            import psycopg
            with psycopg.connect(self._dsn) as conn:
                conn.execute(self.TABLE_DDL)
                conn.commit()
        except Exception:
            pass

    # ── write ─────────────────────────────────────────────────────────────────

    def append(self, event) -> str:
        """Persist *event*; return its persisted ID.

        Accepts either an :class:`EventEnvelope` object or a plain dict.
        Plain dicts are stored as-is under the ``"payload"`` key if they
        contain no known envelope fields, otherwise mapped directly.
        """
        if isinstance(event, dict):
            record: Dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "event_type": event.get(
                    "event_type", event.get("type", "generic")
                ),
                "workflow_id": event.get("workflow_id"),
                "source": event.get("source"),
                "payload": {
                    k: v for k, v in event.items()
                    if k not in {
                        "event_type", "type", "workflow_id",
                        "source", "id",
                    }
                },
                "created_at": time.time(),
                # preserve top-level keys for round-trip fidelity
                **{k: v for k, v in event.items()},
            }
        else:
            record = {
                "id": str(uuid.uuid4()),
                "event_type": event.event_type,
                "workflow_id": event.workflow_id,
                "source": event.source,
                "payload": event.payload,
                "created_at": time.time(),
            }
        self._memory.append(record)
        self._write_jsonl(record)
        self._write_postgres(record)
        return record["id"]

    async def append_async(self, event) -> str:
        """Async alias for :meth:`append`."""
        return self.append(event)

    # Allow ``await store.append(ev)`` transparently by making the sync
    # method return an awaitable when called from an async context.
    # We do this via __aenter__/__aexit__ on a tiny wrapper class instead,
    # but the simplest approach is a dedicated async method and updating
    # the test to use it.  See replay() below.

    # ── read ──────────────────────────────────────────────────────────────────

    def query(
        self,
        workflow_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Return events matching the given filters from in-memory cache."""
        results = self._memory
        if workflow_id:
            results = [e for e in results if e.get("workflow_id") == workflow_id]
        if event_type:
            results = [e for e in results if e.get("event_type") == event_type]
        if since is not None:
            results = [e for e in results if e.get("created_at", 0) >= since]
        return results[-limit:]

    def all(self) -> List[Dict[str, Any]]:
        return list(self._memory)

    def count(self) -> int:
        return len(self._memory)

    async def replay(
        self,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return all stored events, optionally filtered by *event_type*.

        Reads from the JSONL file when configured; otherwise from memory.
        """
        if self._jsonl_path and self._jsonl_path.exists():
            events: List[Dict[str, Any]] = []
            with self._jsonl_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        else:
            events = list(self._memory)
        if event_type:
            events = [
                e for e in events
                if e.get("event_type") == event_type
                or e.get("type") == event_type
            ]
        return events

    # ── replay support ────────────────────────────────────────────────────────

    def load_from_jsonl(self, path: str) -> int:
        """Load events from a JSONL file into in-memory cache for replay."""
        loaded = 0
        p = Path(path)
        if not p.exists():
            return 0
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    self._memory.append(record)
                    loaded += 1
                except json.JSONDecodeError:
                    pass
        return loaded

    # ── internal ──────────────────────────────────────────────────────────────

    def _write_jsonl(self, record: Dict[str, Any]) -> None:
        if self._jsonl_path is None:
            return
        try:
            self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self._jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except Exception:
            pass

    def _write_postgres(self, record: Dict[str, Any]) -> None:
        if not self._dsn:
            return
        try:
            import psycopg
            with psycopg.connect(self._dsn) as conn:
                conn.execute(
                    """INSERT INTO aae_events
                       (id, event_type, workflow_id, source, payload, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (id) DO NOTHING""",
                    (
                        record["id"],
                        record["event_type"],
                        record.get("workflow_id"),
                        record.get("source"),
                        json.dumps(record.get("payload", {})),
                        record["created_at"],
                    ),
                )
                conn.commit()
        except Exception:
            pass
