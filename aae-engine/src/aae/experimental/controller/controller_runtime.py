"""controller_runtime.py — Production-grade deterministic controller runtime.

This module is the backbone of the AAE platform.  Every subsystem (planner,
agents, sandbox, memory) must pass through this runtime.  The runtime
guarantees:

    * Deterministic orchestration — only the controller changes task states.
    * Safe agent execution     — agents run inside a guarded context.
    * Bounded retries          — failures never loop indefinitely.
    * Full event traceability  — every state transition emits a typed event.
    * Cancellation support     — individual tasks or whole workflows may be
                                  cancelled without corrupting shared state.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# ─── Task State ───────────────────────────────────────────────────────────────

class TaskState(Enum):
    CREATED    = "created"
    QUEUED     = "queued"
    PLANNED    = "planned"
    DISPATCHED = "dispatched"
    RUNNING    = "running"
    SUCCEEDED  = "succeeded"
    FAILED     = "failed"
    TIMEOUT    = "timeout"
    CANCELLED  = "cancelled"


# ─── Domain Objects ───────────────────────────────────────────────────────────

@dataclass
class RuntimeTask:
    id: str
    type: str
    payload: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    state: TaskState = TaskState.QUEUED
    retries: int = 0
    max_retries: int = 3
    timeout_s: float = 300.0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class RuntimeEvent:
    id: str
    type: str
    source: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


# ─── Event Bus ────────────────────────────────────────────────────────────────

class RuntimeEventBus:
    """Lightweight, in-process pub/sub for runtime state events."""

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._listeners.setdefault(event_type, []).append(handler)
        self._listeners.setdefault("*", [])

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = RuntimeEvent(
            id=str(uuid.uuid4()),
            type=event_type,
            source="controller_runtime",
            payload=payload,
        )
        for handler in list(self._listeners.get(event_type, [])):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                pass
        for handler in list(self._listeners.get("*", [])):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                pass


# ─── Agent Registry ───────────────────────────────────────────────────────────

class RuntimeAgentRegistry:
    """Maps task types to agent callable objects."""

    def __init__(self) -> None:
        self._agents: Dict[str, Any] = {}

    def register(self, task_type: str, agent: Any) -> None:
        self._agents[task_type] = agent

    def resolve(self, task_type: str) -> Any:
        if task_type not in self._agents:
            raise KeyError("No agent registered for task type '%s'" % task_type)
        return self._agents[task_type]

    def registered_types(self) -> List[str]:
        return list(self._agents.keys())


# ─── Task Scheduler ───────────────────────────────────────────────────────────

class RuntimeTaskScheduler:
    """Priority queue with dependency-aware readiness checks."""

    def __init__(self, max_concurrency: int = 16) -> None:
        self.max_concurrency = max_concurrency
        self._tasks: Dict[str, RuntimeTask] = {}
        self._running: int = 0

    def add(self, task: RuntimeTask) -> None:
        self._tasks[task.id] = task

    def mark_running(self) -> None:
        self._running += 1

    def mark_finished(self) -> None:
        self._running = max(0, self._running - 1)

    def next_ready(self) -> Optional[RuntimeTask]:
        if self._running >= self.max_concurrency:
            return None
        completed_ids = {
            t.id for t in self._tasks.values()
            if t.state == TaskState.SUCCEEDED
        }
        for task in self._tasks.values():
            if task.state != TaskState.QUEUED:
                continue
            if all(dep in completed_ids for dep in task.dependencies):
                return task
        return None

    def get(self, task_id: str) -> Optional[RuntimeTask]:
        return self._tasks.get(task_id)

    def all_tasks(self) -> List[RuntimeTask]:
        return list(self._tasks.values())

    def is_complete(self) -> bool:
        return all(
            t.state in {TaskState.SUCCEEDED, TaskState.FAILED,
                        TaskState.TIMEOUT, TaskState.CANCELLED}
            for t in self._tasks.values()
        )


# ─── Execution Guard ──────────────────────────────────────────────────────────

class ExecutionGuard:
    """Wraps agent execution with timeout and exception safety."""

    async def run(
        self,
        agent: Any,
        task: RuntimeTask,
    ) -> tuple[bool, Any]:
        try:
            coro = agent.execute(task.payload)
            result = await asyncio.wait_for(coro, timeout=task.timeout_s)
            return True, result
        except asyncio.TimeoutError:
            return False, "timeout after %.1fs" % task.timeout_s
        except Exception as exc:
            return False, str(exc)


# ─── Controller Runtime ───────────────────────────────────────────────────────

class ControllerRuntime:
    """Deterministic autonomous engineering controller.

    This is the *single* component allowed to:
        - transition task states
        - dispatch agents
        - emit runtime events

    No other module may change TaskState directly.
    """

    def __init__(
        self,
        max_concurrency: int = 16,
        tick_interval_s: float = 0.05,
    ) -> None:
        self.scheduler = RuntimeTaskScheduler(max_concurrency=max_concurrency)
        self.registry = RuntimeAgentRegistry()
        self.event_bus = RuntimeEventBus()
        self.guard = ExecutionGuard()
        self._running = False
        self._tick_interval = tick_interval_s
        self._loop_task: Optional[asyncio.Task] = None

    # ── task submission ────────────────────────────────────────────────────────

    def submit(
        self,
        task_type: str,
        payload: Dict[str, Any],
        *,
        dependencies: Optional[List[str]] = None,
        max_retries: int = 3,
        timeout_s: float = 300.0,
    ) -> str:
        task = RuntimeTask(
            id=str(uuid.uuid4()),
            type=task_type,
            payload=payload,
            dependencies=dependencies or [],
            max_retries=max_retries,
            timeout_s=timeout_s,
        )
        self.scheduler.add(task)
        return task.id

    def cancel_task(self, task_id: str) -> bool:
        task = self.scheduler.get(task_id)
        if task is None or task.state not in {TaskState.QUEUED, TaskState.PLANNED}:
            return False
        task.state = TaskState.CANCELLED
        task.finished_at = time.time()
        asyncio.create_task(
            self.event_bus.publish("task.cancelled", {"task_id": task_id})
        )
        return True

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        self._loop_task = asyncio.create_task(self._main_loop())
        await self.event_bus.publish("runtime.started", {})

    async def stop(self) -> None:
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        await self.event_bus.publish("runtime.stopped", {})

    async def run_until_complete(self) -> Dict[str, Any]:
        """Block until all submitted tasks reach a terminal state."""
        await self.start()
        while not self.scheduler.is_complete():
            await asyncio.sleep(self._tick_interval)
        await self.stop()
        return self._summarise()

    # ── main loop ─────────────────────────────────────────────────────────────

    async def _main_loop(self) -> None:
        while self._running:
            task = self.scheduler.next_ready()
            if task is not None:
                asyncio.create_task(self._dispatch(task))
            await asyncio.sleep(self._tick_interval)

    async def _dispatch(self, task: RuntimeTask) -> None:
        agent = self.registry.resolve(task.type)
        task.state = TaskState.DISPATCHED
        task.started_at = time.time()
        self.scheduler.mark_running()

        await self.event_bus.publish(
            "task.dispatched",
            {"task_id": task.id, "task_type": task.type},
        )

        success, result = await self.guard.run(agent, task)
        self.scheduler.mark_finished()
        task.finished_at = time.time()

        if success:
            task.state = TaskState.SUCCEEDED
            task.result = result if isinstance(result, dict) else {"output": result}
            await self.event_bus.publish(
                "task.succeeded",
                {"task_id": task.id, "result": task.result},
            )
        else:
            await self._handle_failure(task, str(result))

    async def _handle_failure(self, task: RuntimeTask, error: str) -> None:
        task.retries += 1
        task.error = error

        if "timeout" in error:
            task.state = TaskState.TIMEOUT
            await self.event_bus.publish(
                "task.timeout",
                {"task_id": task.id, "error": error},
            )
            return

        if task.retries <= task.max_retries:
            task.state = TaskState.QUEUED     # back to queue for retry
            await self.event_bus.publish(
                "task.retry",
                {
                    "task_id": task.id,
                    "attempt": task.retries,
                    "max": task.max_retries,
                    "error": error,
                },
            )
        else:
            task.state = TaskState.FAILED
            await self.event_bus.publish(
                "task.failed",
                {"task_id": task.id, "error": error, "retries": task.retries},
            )

    # ── introspection ─────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[RuntimeTask]:
        return self.scheduler.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": t.id,
                "type": t.type,
                "state": t.state.value,
                "retries": t.retries,
                "created_at": t.created_at,
                "started_at": t.started_at,
                "finished_at": t.finished_at,
            }
            for t in self.scheduler.all_tasks()
        ]

    def _summarise(self) -> Dict[str, Any]:
        tasks = self.scheduler.all_tasks()
        return {
            "total": len(tasks),
            "succeeded": sum(1 for t in tasks if t.state == TaskState.SUCCEEDED),
            "failed": sum(1 for t in tasks if t.state == TaskState.FAILED),
            "timeout": sum(1 for t in tasks if t.state == TaskState.TIMEOUT),
            "cancelled": sum(1 for t in tasks if t.state == TaskState.CANCELLED),
        }
