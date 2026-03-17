from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Callable, Dict, List, Optional


_PLANNER_QUEUE = "aae:queue:planner"
_AGENT_QUEUE = "aae:queue:agent"
_SANDBOX_QUEUE = "aae:queue:sandbox"


class DistributedScheduler:
    """Routes tasks to Redis-backed worker queues.

    Falls back to in-process direct dispatch when Redis is unavailable,
    preserving deterministic orchestration in single-node deployments.
    """

    QUEUE_MAP: Dict[str, str] = {
        "plan": _PLANNER_QUEUE,
        "research": _AGENT_QUEUE,
        "security": _AGENT_QUEUE,
        "swe": _AGENT_QUEUE,
        "test": _AGENT_QUEUE,
        "review": _AGENT_QUEUE,
        "sandbox": _SANDBOX_QUEUE,
    }

    def __init__(
        self,
        redis_url: str | None = None,
        local_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.redis_url = redis_url
        self.local_handler = local_handler
        self._redis = None
        self._pending: List[Dict[str, Any]] = []   # local fallback queue

    async def start(self) -> None:
        if not self.redis_url:
            return
        try:
            from redis import asyncio as aioredis
            self._redis = aioredis.from_url(self.redis_url)
        except ImportError:
            self._redis = None

    async def stop(self) -> None:
        if self._redis:
            await self._redis.close()

    # ── dispatch ──────────────────────────────────────────────────────────────

    async def dispatch(self, task_type: str, payload: Dict[str, Any]) -> str:
        """Push a task envelope onto the appropriate worker queue.

        Returns the generated job ID.
        """
        job_id = str(uuid.uuid4())
        envelope: Dict[str, Any] = {
            "job_id": job_id,
            "task_type": task_type,
            "payload": payload,
        }
        queue = self._resolve_queue(task_type)

        if self._redis is not None:
            await self._redis.xadd(queue, {"data": json.dumps(envelope)})
        else:
            self._pending.append(envelope)
            if self.local_handler is not None:
                self.local_handler(envelope)

        return job_id

    # ── consume ───────────────────────────────────────────────────────────────

    async def consume(
        self,
        queues: List[str],
        consumer_id: str,
        batch_size: int = 10,
    ) -> List[Dict[str, Any]]:
        """Pull the next batch of messages from the given queues.

        Returns a (possibly empty) list of envelope dicts.
        """
        if self._redis is None:
            batch = self._pending[:batch_size]
            self._pending = self._pending[batch_size:]
            return batch

        messages: List[Dict[str, Any]] = []
        for queue in queues:
            try:
                results = await self._redis.xread(
                    {queue: "$"}, count=batch_size, block=100
                )
                for _, entries in (results or []):
                    for _msg_id, fields in entries:
                        raw = fields.get(b"data") or fields.get("data", b"{}")
                        messages.append(json.loads(raw))
            except Exception:
                pass
        return messages

    # ── queue depth ───────────────────────────────────────────────────────────

    async def queue_depth(self, queue: str) -> int:
        if self._redis is None:
            return len(self._pending)
        try:
            info = await self._redis.xlen(queue)
            return int(info)
        except Exception:
            return 0

    async def all_queue_depths(self) -> Dict[str, int]:
        result = {}
        for queue in set(self.QUEUE_MAP.values()):
            result[queue] = await self.queue_depth(queue)
        return result

    # ── internal ──────────────────────────────────────────────────────────────

    def _resolve_queue(self, task_type: str) -> str:
        for prefix, queue in self.QUEUE_MAP.items():
            if task_type.startswith(prefix):
                return queue
        return _AGENT_QUEUE
