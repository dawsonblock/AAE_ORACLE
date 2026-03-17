"""cluster/queue_adapter — abstracts the task queue over Redis Streams.

Wraps Redis Streams (or an in-memory fallback) so WorkerNodes can
dequeue tasks without knowing the transport.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_STREAM_MAP = {
    "planner": "aae:queue:planner",
    "agent": "aae:queue:agent",
    "sandbox": "aae:queue:sandbox",
}


class QueueAdapter:
    """Async task queue backed by Redis Streams or in-memory deques.

    Parameters
    ----------
    redis_store:
        Optional ``RedisStore`` instance.  Without it the adapter uses
        in-memory asyncio.Queue objects (single-process only).
    """

    def __init__(self, redis_store: Any | None = None) -> None:
        self._redis = redis_store
        self._local: Dict[str, asyncio.Queue[Dict[str, Any]]] = (
            defaultdict(asyncio.Queue)
        )
        self._last_ids: Dict[str, str] = defaultdict(lambda: "$")

    async def dispatch(
        self,
        task: Dict[str, Any],
        worker_type: str = "agent",
    ) -> str:
        """Enqueue *task* for *worker_type*. Returns a task ID."""
        task_id = task.setdefault("task_id", str(uuid.uuid4()))
        if self._redis:
            stream = _STREAM_MAP.get(worker_type, "aae:queue:agent")
            await self._redis.xadd(stream, task)
        else:
            await self._local[worker_type].put(task)
        log.debug(
            "queue dispatch task_id=%s worker_type=%s", task_id, worker_type
        )
        return task_id

    async def consume(
        self,
        worker_type: str = "agent",
        timeout: float = 2.0,
    ) -> Optional[Dict[str, Any]]:
        """Dequeue one task for *worker_type*, or return None on timeout."""
        if self._redis:
            return await self._consume_redis(worker_type, timeout)
        return await self._consume_local(worker_type, timeout)

    async def depth(self, worker_type: str = "agent") -> int:
        """Return approximate queue depth."""
        if self._redis:
            stream = _STREAM_MAP.get(worker_type, "aae:queue:agent")
            try:
                client = self._redis._client  # type: ignore[attr-defined]
                if client:
                    info = await client.xinfo_stream(
                        self._redis._prefix + stream
                    )
                    return int(info.get("length", 0))
            except Exception:
                pass
        q = self._local.get(worker_type)
        return q.qsize() if q else 0

    async def all_depths(self) -> Dict[str, int]:
        return {wt: await self.depth(wt) for wt in _STREAM_MAP}

    # ── internal ──────────────────────────────────────────────────────────────

    async def _consume_redis(
        self, worker_type: str, timeout: float
    ) -> Optional[Dict[str, Any]]:
        stream = _STREAM_MAP.get(worker_type, "aae:queue:agent")
        last_id = self._last_ids[worker_type]
        block_ms = int(timeout * 1000)
        try:
            raw = await self._redis.xread(  # type: ignore[attr-defined]
                stream, last_id=last_id, count=1, block_ms=block_ms
            )
        except Exception as exc:
            log.debug("redis xread error: %s", exc)
            return None
        if not raw:
            return None
        stream_key, messages = raw[0]
        msg_id, data = messages[0]
        self._last_ids[worker_type] = msg_id
        return {k: self._deserialise(v) for k, v in data.items()}

    async def _consume_local(
        self, worker_type: str, timeout: float
    ) -> Optional[Dict[str, Any]]:
        q = self._local[worker_type]
        try:
            return await asyncio.wait_for(q.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    @staticmethod
    def _deserialise(val: Any) -> Any:
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val
