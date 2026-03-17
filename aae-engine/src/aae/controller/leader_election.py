from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Callable, Dict, Optional


class LeaderElection:
    """Simple leader-election mechanism backed by Redis SETNX.

    In single-node or test mode (no Redis URL), the instance always
    considers itself the leader so the controller can run without
    external infrastructure.

    Usage::

        election = LeaderElection(redis_url=os.getenv("REDIS_URL"))
        await election.start()
        if election.is_leader:
            # perform leader-only work
    """

    KEY = "aae:controller:leader"
    HEARTBEAT_INTERVAL = 5.0    # seconds
    TTL_SECONDS = 15            # Redis key TTL; must be > 2 × heartbeat

    def __init__(
        self,
        redis_url: str | None = None,
        node_id: str | None = None,
        on_gained: Optional[Callable[[], None]] = None,
        on_lost: Optional[Callable[[], None]] = None,
    ) -> None:
        self.redis_url = redis_url
        self.node_id = node_id or os.getenv("AAE_NODE_ID", str(uuid.uuid4())[:8])
        self.on_gained = on_gained
        self.on_lost = on_lost
        self._is_leader = False
        self._redis = None
        self._task: Optional[asyncio.Task] = None

    @property
    def is_leader(self) -> bool:
        """True when this node holds the leadership token."""
        if self._redis is None:
            return True  # single-node fallback
        return self._is_leader

    async def start(self) -> None:
        """Begin campaigning for leadership."""
        if not self.redis_url:
            self._is_leader = True
            return
        try:
            from redis import asyncio as aioredis
            self._redis = aioredis.from_url(self.redis_url)
        except ImportError:
            self._is_leader = True
            return
        self._task = asyncio.create_task(self._campaign_loop())

    async def stop(self) -> None:
        """Resign leadership and stop the heartbeat loop."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._redis and self._is_leader:
            try:
                current = await self._redis.get(self.KEY)
                if current and current.decode() == self.node_id:
                    await self._redis.delete(self.KEY)
            except Exception:
                pass
        self._is_leader = False
        if self._redis:
            await self._redis.close()

    # ── internal ──────────────────────────────────────────────────────────────

    async def _campaign_loop(self) -> None:
        while True:
            try:
                acquired = await self._try_acquire()
                if acquired and not self._is_leader:
                    self._is_leader = True
                    if self.on_gained:
                        self.on_gained()
                elif not acquired and self._is_leader:
                    self._is_leader = False
                    if self.on_lost:
                        self.on_lost()
            except Exception:
                pass
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

    async def _try_acquire(self) -> bool:
        """Attempt to set or refresh the leader key."""
        set_result = await self._redis.set(
            self.KEY,
            self.node_id,
            ex=self.TTL_SECONDS,
            nx=True,  # only set if not exists
        )
        if set_result:
            return True
        # Already holding the key — refresh TTL
        current = await self._redis.get(self.KEY)
        if current and current.decode() == self.node_id:
            await self._redis.expire(self.KEY, self.TTL_SECONDS)
            return True
        return False

    # ── diagnostics ───────────────────────────────────────────────────────────

    def status(self) -> Dict[str, object]:
        return {
            "node_id": self.node_id,
            "is_leader": self.is_leader,
            "backend": "redis" if self._redis else "single-node",
        }
