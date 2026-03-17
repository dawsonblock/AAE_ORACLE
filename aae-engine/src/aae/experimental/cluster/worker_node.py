"""cluster/worker_node — represents a single distributed worker process.

A WorkerNode registers itself with the cluster, polls a task queue,
executes tasks through a local ExecutionRouter, and reports results back.
"""
from __future__ import annotations

import asyncio
import logging
import platform
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    OFFLINE = "offline"


@dataclass
class NodeInfo:
    node_id: str
    hostname: str
    worker_type: str          # "planner" | "agent" | "sandbox"
    status: NodeStatus = NodeStatus.IDLE
    current_task: Optional[str] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    started_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)

    def uptime(self) -> float:
        return time.time() - self.started_at


class WorkerNode:
    """Async worker that dequeues and executes tasks.

    Parameters
    ----------
    worker_type:
        Logical role of this worker (planner / agent / sandbox).
    queue_adapter:
        Queue from which to consume tasks.
    execution_router:
        Handles the actual task execution.
    task_callback:
        Called with ``(task_id, result)`` after each execution.
    concurrency:
        Max parallel tasks per node.
    poll_interval:
        Seconds between queue poll attempts when queue is empty.
    """

    def __init__(
        self,
        worker_type: str,
        queue_adapter: Any | None = None,
        execution_router: Any | None = None,
        task_callback: Optional[Callable[[str, Any], None]] = None,
        concurrency: int = 1,
        poll_interval: float = 2.0,
        # convenience aliases used by scripts and tests
        node_id: Optional[str] = None,
        queue_name: Optional[str] = None,  # noqa: F841 (stored for informational use)
        execute_fn: Optional[Callable] = None,
    ) -> None:
        self.info = NodeInfo(
            node_id=node_id or str(uuid.uuid4()),
            hostname=platform.node(),
            worker_type=worker_type,
        )
        self._queue = queue_adapter
        self._queue_name = queue_name
        self._router = execution_router
        self._execute_fn = execute_fn
        self._callback = task_callback
        self._concurrency = concurrency
        self._poll_interval = poll_interval
        self._sem = asyncio.Semaphore(concurrency)
        self._running = False
        self._tasks: List[asyncio.Task[None]] = []

    @property
    def node_id(self) -> str:
        return self.info.node_id

    async def _execute_one(self, task: Dict[str, Any]) -> Any:
        """Public single-task execution entry-point (used by scripts & tests)."""
        if self._execute_fn is not None:
            return await self._execute_fn(task)
        return await self._run_task(task)

    async def start(self) -> None:
        self._running = True
        self.info.status = NodeStatus.IDLE
        log.info(
            "worker_node id=%s type=%s started",
            self.info.node_id[:8],
            self.info.worker_type,
        )
        self._tasks.append(asyncio.create_task(self._poll_loop()))
        self._tasks.append(asyncio.create_task(self._heartbeat_loop()))

    async def stop(self) -> None:
        self._running = False
        self.info.status = NodeStatus.DRAINING
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self.info.status = NodeStatus.OFFLINE
        log.info("worker_node id=%s stopped", self.info.node_id[:8])

    def status(self) -> Dict[str, Any]:
        return {
            "node_id": self.info.node_id,
            "hostname": self.info.hostname,
            "worker_type": self.info.worker_type,
            "status": self.info.status.value,
            "tasks_completed": self.info.tasks_completed,
            "tasks_failed": self.info.tasks_failed,
            "uptime_s": self.info.uptime(),
        }

    async def _poll_loop(self) -> None:
        while self._running:
            # Wait for a concurrency slot before dequeueing the next task so
            # we don't pull work we cannot immediately start.
            await self._sem.acquire()
            task = await self._dequeue()
            if task is None:
                self._sem.release()
                await asyncio.sleep(self._poll_interval)
                continue
            # Dispatch execution as an independent task so the poll loop can
            # immediately cycle back and dequeue the next item.
            asyncio.create_task(self._dispatch(task))

    async def _heartbeat_loop(self) -> None:
        while self._running:
            self.info.last_heartbeat = time.time()
            await asyncio.sleep(10)

    async def _dispatch(self, task: Dict[str, Any]) -> None:
        """Run *task* then release the concurrency semaphore."""
        try:
            await self._execute(task)
        finally:
            self._sem.release()

    async def _run_task(self, task: Dict[str, Any]) -> Any:
        """Execute via router or execute_fn; return result."""
        if self._execute_fn is not None:
            return await self._execute_fn(task)
        if self._router:
            return await self._router.route(
                action=task.get("action", "run_command"),
                payload=task.get("payload", {}),
                timeout=float(task.get("timeout", 120)),
            )
        await asyncio.sleep(0.1)
        return {"status": "dry_run"}

    async def _dequeue(self) -> Optional[Dict[str, Any]]:
        if self._queue is None:
            await asyncio.sleep(self._poll_interval)
            return None
        try:
            return await self._queue.consume(worker_type=self.info.worker_type)
        except Exception as exc:
            log.debug("dequeue error: %s", exc)
            return None

    async def _execute(self, task: Dict[str, Any]) -> None:
        task_id = task.get("task_id", "?")
        self.info.status = NodeStatus.BUSY
        self.info.current_task = task_id
        try:
            result = await self._run_task(task)
            self.info.tasks_completed += 1
            if self._callback:
                self._callback(task_id, result)
        except Exception as exc:
            self.info.tasks_failed += 1
            log.error("task %s failed: %s", task_id, exc)
        finally:
            self.info.status = NodeStatus.IDLE
            self.info.current_task = None
