"""execution_fabric/fabric_controller — top-level coordinator for the fabric.

The FabricController owns the lifecycle of all fabric components:
queue, workers, heartbeat monitor, and load balancer.  It is the single
entry point that the ControllerRuntime calls to submit execution tasks.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class FabricController:
    """Orchestrates the entire distributed execution fabric.

    Parameters
    ----------
    queue_adapter / worker_manager / heartbeat_monitor / load_balancer:
        Fabric sub-components.  All are optional for graceful degradation.
    """

    def __init__(
        self,
        queue_adapter: Any | None = None,
        worker_manager: Any | None = None,
        heartbeat_monitor: Any | None = None,
        load_balancer: Any | None = None,
    ) -> None:
        self._queue = queue_adapter
        self._workers = worker_manager
        self._heartbeat = heartbeat_monitor
        self._lb = load_balancer
        self._running = False

    async def start(self) -> None:
        """Start all fabric components."""
        self._running = True
        if self._workers:
            await self._workers.start()
        if self._heartbeat:
            await self._heartbeat.start()
        log.info("FabricController started")

    async def stop(self) -> None:
        """Gracefully shut down all fabric components."""
        self._running = False
        if self._heartbeat:
            await self._heartbeat.stop()
        if self._workers:
            await self._workers.stop()
        log.info("FabricController stopped")

    async def submit(
        self,
        task: Dict[str, Any],
        worker_type: Optional[str] = None,
    ) -> str:
        """Submit *task* to the fabric. Returns task ID."""
        if self._lb and worker_type:
            worker_type = await self._lb.select(worker_type)
        if self._queue:
            return await self._queue.dispatch(
                task, worker_type=worker_type or "agent"
            )
        # Dry-run fallback
        task_id = task.get("task_id", "dry-run")
        log.warning("no queue adapter; task %s not dispatched", task_id)
        return task_id

    async def submit_batch(
        self, tasks: List[Dict[str, Any]], worker_type: Optional[str] = None
    ) -> List[str]:
        """Submit multiple tasks concurrently."""
        coros = [self.submit(t, worker_type) for t in tasks]
        return list(await asyncio.gather(*coros))

    async def status(self) -> Dict[str, Any]:
        """Return a snapshot of fabric health."""
        result: Dict[str, Any] = {"running": self._running}
        if self._queue:
            result["queue_depths"] = await self._queue.all_depths()
        if self._workers:
            result["workers"] = self._workers.status()
        if self._heartbeat:
            result["unhealthy_nodes"] = self._heartbeat.unhealthy()
        return result

    async def scale(self, worker_type: str, count: int) -> None:
        """Scale workers of *worker_type* to *count*."""
        if self._workers and hasattr(self._workers, "scale_to"):
            await self._workers.scale_to(count)
