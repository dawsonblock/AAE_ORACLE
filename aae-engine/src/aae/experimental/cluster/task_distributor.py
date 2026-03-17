"""cluster/task_distributor — routes tasks from controller to worker queues.

The controller calls ``TaskDistributor.dispatch()`` with a task dict and
the distributor chooses the right queue (planner / agent / sandbox) based
on the task's ``kind`` field, then optionally applies load-aware routing.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# Map task kinds to worker types
_KIND_TO_WORKER: Dict[str, str] = {
    "plan": "planner",
    "replan": "planner",
    "research": "agent",
    "security_scan": "agent",
    "test": "agent",
    "review": "agent",
    "run_tests": "sandbox",
    "sandbox_exec": "sandbox",
    "apply_patch": "sandbox",
}


class TaskDistributor:
    """Route controller tasks to the appropriate worker queue.

    Parameters
    ----------
    queue_adapter:
        ``QueueAdapter`` that backs the queues.
    load_balancer:
        Optional ``LoadBalancer`` for capacity-aware routing.
    """

    def __init__(
        self,
        queue_adapter: Any | None = None,
        load_balancer: Any | None = None,
    ) -> None:
        self._queue = queue_adapter
        self._lb = load_balancer

    async def dispatch(
        self,
        task: Dict[str, Any],
        worker_type: Optional[str] = None,
    ) -> str:
        """Dispatch *task* to the appropriate queue.

        Returns the assigned task ID.
        """
        if worker_type is None:
            worker_type = self._resolve_worker_type(task)

        if self._lb:
            worker_type = await self._lb.select(worker_type)

        if self._queue:
            task_id = await self._queue.dispatch(task, worker_type=worker_type)
        else:
            task_id = task.get("task_id", "noop")
            log.warning("no queue adapter; task %s dropped", task_id)

        log.debug("distributed task=%s to %s", task_id, worker_type)
        return task_id

    async def dispatch_batch(
        self, tasks: list[Dict[str, Any]]
    ) -> list[str]:
        """Dispatch multiple tasks and return their IDs."""
        import asyncio
        coros = [self.dispatch(t) for t in tasks]
        return list(await asyncio.gather(*coros))

    async def queue_depths(self) -> Dict[str, int]:
        if self._queue:
            return await self._queue.all_depths()
        return {}

    def _resolve_worker_type(self, task: Dict[str, Any]) -> str:
        kind = str(task.get("kind", "agent"))
        return _KIND_TO_WORKER.get(kind, "agent")
