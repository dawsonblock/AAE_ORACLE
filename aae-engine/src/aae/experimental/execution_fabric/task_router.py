"""execution_fabric/task_router — routes tasks within the fabric."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


class TaskRouter:
    """Route tasks to fabric queues with priority support.

    Parameters
    ----------
    queue_adapter:
        ``FabricQueueAdapter`` instance.
    default_worker_type:
        Fallback when no routing rule matches.
    """

    _PRIORITY_MAP: Dict[str, int] = {
        "security_scan": 10,
        "apply_patch": 8,
        "run_tests": 7,
        "plan": 5,
        "research": 3,
    }

    def __init__(
        self,
        queue_adapter: Any | None = None,
        default_worker_type: str = "agent",
    ) -> None:
        self._queue = queue_adapter
        self._default = default_worker_type

    async def route(
        self,
        task: Dict[str, Any],
        worker_type: Optional[str] = None,
    ) -> str:
        """Route *task* to the most appropriate queue."""
        wtype = worker_type or self._default
        priority = self._PRIORITY_MAP.get(
            str(task.get("kind", "")), 0
        )
        task.setdefault("priority", priority)
        if self._queue:
            return await self._queue.dispatch(task, worker_type=wtype)
        return task.get("task_id", "dry-run")

    async def route_batch(
        self, tasks: list[Dict[str, Any]]
    ) -> list[str]:
        import asyncio
        return list(await asyncio.gather(*(self.route(t) for t in tasks)))
