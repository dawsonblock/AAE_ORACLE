"""redis_store — async Redis-backed ephemeral store for AAE.

Used for:
- Distributed locks (leader election heartbeats)
- Task queue depth counters
- Short-lived caches (localization results, plan hashes)
- Pub/sub event fan-out
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class RedisStore:
    """Async Redis wrapper with graceful in-memory fallback.

    If ``redis-py`` is not installed or the server is unreachable the store
    silently degrades to an in-process dict (no TTL enforcement, no pub/sub).

    Parameters
    ----------
    url:
        Redis URL, e.g. ``redis://localhost:6379/0``.
    prefix:
        Key prefix to namespace all AAE keys.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        prefix: str = "aae:",
    ) -> None:
        self._url = url
        self._prefix = prefix
        self._client: Any = None
        self._fallback: Dict[str, str] = {}

    async def connect(self) -> None:
        """Open the Redis connection pool."""
        try:
            import redis.asyncio as aioredis  # type: ignore[import]

            self._client = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._client.ping()
            log.info("RedisStore connected to %s", self._url)
        except Exception as exc:
            log.warning("RedisStore unavailable (%s); using fallback", exc)
            self._client = None

    async def close(self) -> None:
        if self._client:
            await self._client.close()

    def available(self) -> bool:
        return self._client is not None

    # ── string KV ─────────────────────────────────────────────────────────────

    async def set(self, key: str, value: Any, ttl: int = 0) -> None:
        k = self._k(key)
        raw = json.dumps(value)
        if self._client:
            if ttl > 0:
                await self._client.setex(k, ttl, raw)
            else:
                await self._client.set(k, raw)
        else:
            self._fallback[k] = raw

    async def get(self, key: str) -> Optional[Any]:
        k = self._k(key)
        if self._client:
            raw = await self._client.get(k)
        else:
            raw = self._fallback.get(k)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    async def delete(self, key: str) -> bool:
        k = self._k(key)
        if self._client:
            return bool(await self._client.delete(k))
        return bool(self._fallback.pop(k, None) is not None)

    async def exists(self, key: str) -> bool:
        k = self._k(key)
        if self._client:
            return bool(await self._client.exists(k))
        return k in self._fallback

    async def keys(self, pattern: str = "*") -> List[str]:
        if self._client:
            full_pattern = self._prefix + pattern
            raw = await self._client.keys(full_pattern)
            return [k[len(self._prefix):] for k in raw]
        p = self._prefix + pattern.replace("*", "")
        return [k[len(self._prefix):] for k in self._fallback if k.startswith(p)]

    # ── atomic ops ────────────────────────────────────────────────────────────

    async def setnx(self, key: str, value: Any, ttl: int = 0) -> bool:
        """Set if not exists. Return True if the key was set."""
        k = self._k(key)
        raw = json.dumps(value)
        if self._client:
            if ttl > 0:
                return bool(
                    await self._client.set(k, raw, nx=True, ex=ttl)
                )
            return bool(await self._client.setnx(k, raw))
        if k not in self._fallback:
            self._fallback[k] = raw
            return True
        return False

    async def incr(self, key: str, amount: int = 1) -> int:
        k = self._k(key)
        if self._client:
            return int(await self._client.incrby(k, amount))
        current = int(json.loads(self._fallback.get(k, "0")))
        current += amount
        self._fallback[k] = json.dumps(current)
        return current

    async def expire(self, key: str, ttl: int) -> None:
        k = self._k(key)
        if self._client:
            await self._client.expire(k, ttl)

    # ── streams ───────────────────────────────────────────────────────────────

    async def xadd(
        self,
        stream: str,
        data: Dict[str, Any],
        maxlen: int = 1000,
    ) -> Optional[str]:
        """Append a message to a Redis stream, return the message ID."""
        if not self._client:
            return None
        raw = {k: json.dumps(v) for k, v in data.items()}
        msg_id = await self._client.xadd(
            self._k(stream), raw, maxlen=maxlen, approximate=True
        )
        return msg_id

    async def xread(
        self,
        stream: str,
        last_id: str = "0",
        count: int = 10,
        block_ms: int = 0,
    ) -> List[Any]:
        if not self._client:
            return []
        key = self._k(stream)
        raw = await self._client.xread(
            {key: last_id}, count=count, block=block_ms or None
        )
        return raw or []

    # ── pub/sub ───────────────────────────────────────────────────────────────

    async def publish(self, channel: str, message: Any) -> int:
        if not self._client:
            return 0
        return int(
            await self._client.publish(self._k(channel), json.dumps(message))
        )

    # ── internal ──────────────────────────────────────────────────────────────

    def _k(self, key: str) -> str:
        return self._prefix + key
