"""tests/unit/test_storage.py — unit tests for storage subsystem."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# ArtifactStore
# ---------------------------------------------------------------------------

class TestArtifactStore:
    def test_import(self):
        from aae.storage.artifact_store import ArtifactStore
        assert ArtifactStore is not None

    @pytest.mark.asyncio
    async def test_write_and_read(self, tmp_path):
        from aae.storage.artifact_store import ArtifactStore
        store = ArtifactStore(root=tmp_path)
        content = b"hello world"
        sha = await store.write("test.txt", content)
        assert sha is not None
        retrieved = await store.read(sha)
        assert retrieved == content

    @pytest.mark.asyncio
    async def test_dedup_same_content(self, tmp_path):
        from aae.storage.artifact_store import ArtifactStore
        store = ArtifactStore(root=tmp_path)
        content = b"deduplicated content"
        id1 = await store.write("a.txt", content)
        id2 = await store.write("b.txt", content)
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_read_missing_returns_none(self, tmp_path):
        from aae.storage.artifact_store import ArtifactStore
        store = ArtifactStore(root=tmp_path)
        result = await store.read("a" * 64)  # unknown sha
        assert result is None


# ---------------------------------------------------------------------------
# RedisStore (mocked)
# ---------------------------------------------------------------------------

class TestRedisStore:
    def test_import(self):
        from aae.storage.redis_store import RedisStore
        assert RedisStore is not None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        from aae.storage.redis_store import RedisStore
        # Use fallback mode (no real Redis) by not calling connect()
        store = RedisStore(url="redis://localhost:6379/0")
        # _client is None → falls back to in-memory dict
        await store.set("key", "value")
        result = await store.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        from aae.storage.redis_store import RedisStore
        store = RedisStore()
        result = await store.get("missing_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing(self):
        from aae.storage.redis_store import RedisStore
        store = RedisStore()
        await store.set("del_key", 42)
        deleted = await store.delete("del_key")
        assert deleted is True
        result = await store.get("del_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_setnx(self):
        from aae.storage.redis_store import RedisStore
        store = RedisStore()
        first = await store.setnx("nx_key", "v1")
        second = await store.setnx("nx_key", "v2")
        assert first is True
        assert second is False
        result = await store.get("nx_key")
        assert result == "v1"


# ---------------------------------------------------------------------------
# PostgresStore (mocked via fallback)
# ---------------------------------------------------------------------------

class TestPostgresStore:
    def test_import(self):
        from aae.storage.postgres_store import PostgresStore
        assert PostgresStore is not None

    @pytest.mark.asyncio
    async def test_kv_set_and_get_fallback(self):
        """When pool is None (no Postgres), kv ops are no-ops; graceful."""
        from aae.storage.postgres_store import PostgresStore
        store = PostgresStore(dsn="postgresql://test@localhost/test")
        # pool is None → methods return without error
        await store.kv_set("ns:key", {"data": 1})
        result = await store.kv_get("ns:key")
        assert result is None  # no-op fallback returns None

    @pytest.mark.asyncio
    async def test_kv_delete_fallback(self):
        from aae.storage.postgres_store import PostgresStore
        store = PostgresStore(dsn="postgresql://test@localhost/test")
        deleted = await store.kv_delete("any:key")
        assert deleted is False  # no-op returns False
