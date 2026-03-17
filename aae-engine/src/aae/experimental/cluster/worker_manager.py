"""cluster/worker_manager — lifecycle manager for a pool of WorkerNodes.

Starts, stops, and health-checks a configurable number of workers per
type.  Supports dynamic scaling: add/remove workers at runtime.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .worker_node import WorkerNode

log = logging.getLogger(__name__)


class WorkerManager:
    """Manage a pool of WorkerNode instances.

    Parameters
    ----------
    worker_type:
        Logical role passed to each WorkerNode.
    initial_count:
        Number of workers to start on ``start()``.
    max_count:
        Hard ceiling on concurrent workers.
    queue_adapter / execution_router:
        Shared by all managed workers.
    """

    def __init__(
        self,
        worker_type: str = "generic",
        initial_count: int = 2,
        max_count: int = 16,
        queue_adapter: Any | None = None,
        execution_router: Any | None = None,
    ) -> None:
        self.worker_type = worker_type
        self.initial_count = initial_count
        self.max_count = max_count
        self._queue = queue_adapter
        self._router = execution_router
        self._workers: List[WorkerNode] = []
        # lightweight registry for manually registered worker metadata
        self._registry: Dict[str, Dict[str, Any]] = {}

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the initial pool of workers."""
        for _ in range(self.initial_count):
            await self._add_worker()
        log.info(
            "WorkerManager type=%s started %d workers",
            self.worker_type,
            len(self._workers),
        )

    async def stop(self) -> None:
        """Gracefully stop all workers."""
        await asyncio.gather(
            *(w.stop() for w in self._workers), return_exceptions=True
        )
        self._workers.clear()
        log.info("WorkerManager type=%s stopped", self.worker_type)

    async def scale_to(self, count: int) -> None:
        """Resize the pool to *count* workers."""
        count = min(count, self.max_count)
        while len(self._workers) < count:
            await self._add_worker()
        while len(self._workers) > count:
            w = self._workers.pop()
            await w.stop()

    async def scale_up(self, n: int = 1) -> int:
        added = 0
        for _ in range(n):
            if len(self._workers) < self.max_count:
                await self._add_worker()
                added += 1
        return added

    async def scale_down(self, n: int = 1) -> int:
        removed = 0
        for _ in range(min(n, len(self._workers))):
            w = self._workers.pop()
            await w.stop()
            removed += 1
        return removed

    def count(self) -> int:
        return len(self._workers)

    def status(self) -> List[Dict[str, Any]]:
        return [w.status() for w in self._workers]

    # ── manual registry (for external workers / tests) ────────────────────────

    def register(self, worker_id: str, info: Dict[str, Any]) -> None:
        """Register an external worker by ID (does not start a WorkerNode)."""
        self._registry[worker_id] = info
        log.debug("registered worker %s", worker_id)

    def deregister(self, worker_id: str) -> bool:
        """Deregister a previously registered worker. Returns True if found."""
        if worker_id in self._registry:
            del self._registry[worker_id]
            log.debug("deregistered worker %s", worker_id)
            return True
        return False

    def list_workers(self) -> Dict[str, Dict[str, Any]]:
        """Return all registered workers (registry + managed nodes)."""
        result = dict(self._registry)
        for w in self._workers:
            result[w.node_id] = w.status()
        return result

    def unhealthy(self) -> List[str]:
        """Return node IDs that have not sent a heartbeat in 30 s."""
        threshold = time.time() - 30
        return [
            w.info.node_id
            for w in self._workers
            if w.info.last_heartbeat < threshold
        ]

    async def _add_worker(self) -> WorkerNode:
        w = WorkerNode(
            worker_type=self.worker_type,
            queue_adapter=self._queue,
            execution_router=self._router,
        )
        self._workers.append(w)
        await w.start()
        return w
