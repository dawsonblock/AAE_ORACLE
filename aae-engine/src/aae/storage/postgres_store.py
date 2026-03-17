"""postgres_store — async Postgres KV / row store for durable AAE state.

Provides idiomatic async methods for CRUD operations over two tables:
- ``aae_kv``        ← arbitrary key-value metadata
- ``aae_checkpoints`` ← workflow checkpoint blobs
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class PostgresStore:
    """Thin async wrapper over psycopg3 for AAE persistence.

    Parameters
    ----------
    dsn:
        PostgreSQL connection string, e.g.
        ``postgresql://user:pass@host:5432/db``.
    """

    DDL = """
        CREATE TABLE IF NOT EXISTS aae_kv (
            key         TEXT PRIMARY KEY,
            value       JSONB NOT NULL,
            updated_at  DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())
        );
        CREATE TABLE IF NOT EXISTS aae_checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            workflow_id   TEXT NOT NULL,
            state         JSONB NOT NULL,
            created_at    DOUBLE PRECISION NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_checkpoints_wf
            ON aae_checkpoints(workflow_id);
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Any = None

    async def connect(self) -> None:
        """Open the connection pool."""
        try:
            import psycopg_pool  # type: ignore[import]
            self._pool = psycopg_pool.AsyncConnectionPool(
                self._dsn, min_size=1, max_size=5, open=False
            )
            await self._pool.open()
            await self._migrate()
            log.info("PostgresStore connected")
        except Exception as exc:
            log.warning("PostgresStore unavailable: %s", exc)
            self._pool = None

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    # ── KV store ──────────────────────────────────────────────────────────────

    async def kv_set(self, key: str, value: Any) -> None:
        if not self._pool:
            return
        async with self._pool.connection() as conn:
            await conn.execute(
                "INSERT INTO aae_kv (key, value, updated_at) "
                "VALUES (%s, %s::jsonb, EXTRACT(EPOCH FROM NOW())) "
                "ON CONFLICT (key) DO UPDATE "
                "SET value = EXCLUDED.value, "
                "    updated_at = EXCLUDED.updated_at",
                (key, json.dumps(value)),
            )

    async def kv_get(self, key: str) -> Optional[Any]:
        if not self._pool:
            return None
        async with self._pool.connection() as conn:
            row = await conn.fetchone(
                "SELECT value FROM aae_kv WHERE key = %s", (key,)
            )
        return row[0] if row else None

    async def kv_delete(self, key: str) -> bool:
        if not self._pool:
            return False
        async with self._pool.connection() as conn:
            result = await conn.execute(
                "DELETE FROM aae_kv WHERE key = %s", (key,)
            )
        return bool(result.rowcount)

    async def kv_list(self, prefix: str = "") -> List[str]:
        if not self._pool:
            return []
        async with self._pool.connection() as conn:
            rows = await conn.fetch(
                "SELECT key FROM aae_kv WHERE key LIKE %s ORDER BY key",
                (prefix + "%",),
            )
        return [r[0] for r in rows]

    # ── checkpoint store ──────────────────────────────────────────────────────

    async def save_checkpoint(
        self,
        checkpoint_id: str,
        workflow_id: str,
        state: Dict[str, Any],
        created_at: float,
    ) -> None:
        if not self._pool:
            return
        async with self._pool.connection() as conn:
            await conn.execute(
                "INSERT INTO aae_checkpoints "
                "(checkpoint_id, workflow_id, state, created_at) "
                "VALUES (%s, %s, %s::jsonb, %s) "
                "ON CONFLICT (checkpoint_id) DO UPDATE "
                "SET state = EXCLUDED.state",
                (checkpoint_id, workflow_id, json.dumps(state), created_at),
            )

    async def load_checkpoint(
        self, checkpoint_id: str
    ) -> Optional[Dict[str, Any]]:
        if not self._pool:
            return None
        async with self._pool.connection() as conn:
            row = await conn.fetchone(
                "SELECT state FROM aae_checkpoints "
                "WHERE checkpoint_id = %s",
                (checkpoint_id,),
            )
        return row[0] if row else None

    async def list_checkpoints(
        self, workflow_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        if not self._pool:
            return []
        async with self._pool.connection() as conn:
            rows = await conn.fetch(
                "SELECT checkpoint_id, created_at FROM aae_checkpoints "
                "WHERE workflow_id = %s ORDER BY created_at DESC LIMIT %s",
                (workflow_id, limit),
            )
        return [{"checkpoint_id": r[0], "created_at": r[1]} for r in rows]

    # ── migration ─────────────────────────────────────────────────────────────

    async def _migrate(self) -> None:
        if not self._pool:
            return
        async with self._pool.connection() as conn:
            await conn.execute(self.DDL)
