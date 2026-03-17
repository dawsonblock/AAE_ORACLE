from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from aae.events.event_bus import EventBus
from aae.events.event_logger import EventLogger
from aae.memory.in_memory import InMemoryMemoryStore


class Runtime:
    """High-level runtime facade that wires all subsystems together.

    Provides a simple sequential boot API matching the spec boot sequence::

        runtime = Runtime()
        runtime.start_storage()
        runtime.start_event_bus()
        runtime.start_memory()
        runtime.start_controller()
        runtime.start_agents()
        runtime.start_sandbox()
    """

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._started: List[str] = []

        # Sub-system handles (populated lazily)
        self.event_bus: Optional[EventBus] = None
        self.memory: Optional[InMemoryMemoryStore] = None

    # ── boot phases ───────────────────────────────────────────────────────────

    def start_storage(self) -> None:
        """Phase 1 — initialise persistent storage connections."""
        dsn = os.getenv("AAE_DATABASE_URL", "")
        if dsn:
            from aae.persistence.db import PostgresDatabase
            db = PostgresDatabase(dsn)
            if db.enabled:
                db.execute_ddl(
                    "CREATE TABLE IF NOT EXISTS aae_checkpoints "
                    "(id TEXT PRIMARY KEY, state JSONB, updated_at DOUBLE PRECISION)"
                )
        self._started.append("storage")

    def start_event_bus(self) -> None:
        """Phase 2 — start event bus (in-memory or Redis)."""
        redis_url = os.getenv("REDIS_URL")
        artifacts_dir = self._config.get("artifacts_dir", ".artifacts")
        self.event_bus = EventBus(
            logger=EventLogger(artifacts_dir=artifacts_dir),
            redis_url=redis_url,
        )
        self._started.append("event_bus")

    def start_memory(self) -> None:
        """Phase 3 — start memory subsystem."""
        self.memory = InMemoryMemoryStore()
        self._started.append("memory")

    def start_controller(self) -> None:
        """Phase 4 — start the workflow controller."""
        from aae.controller.agent_registry import AgentRegistry
        from aae.controller.controller import WorkflowController
        from aae.controller.task_scheduler import TaskScheduler
        from aae.controller.retry_policy import RetryPolicy

        registry = AgentRegistry()
        self.controller = WorkflowController(
            registry=registry,
            memory=self.memory or InMemoryMemoryStore(),
            event_bus=self.event_bus or EventBus(),
            scheduler=TaskScheduler(
                max_concurrency=self._config.get("max_concurrency", 8)
            ),
            retry_policy=RetryPolicy(),
        )
        self._started.append("controller")

    def start_agents(self) -> None:
        """Phase 5 — register agent workers with the controller."""
        self._started.append("agents")

    def start_sandbox(self) -> None:
        """Phase 6 — initialise sandbox execution cluster."""
        from aae.sandbox.sandbox_manager import SandboxManager
        self.sandbox = SandboxManager()
        self._started.append("sandbox")

    async def boot_async(self) -> None:
        """Convenience: run all boot phases in order asynchronously."""
        self.start_storage()
        self.start_event_bus()
        self.start_memory()
        self.start_controller()
        self.start_agents()
        self.start_sandbox()
        if self.event_bus:
            await self.event_bus.start()

    async def shutdown(self) -> None:
        if self.event_bus:
            await self.event_bus.close()

    # ── status ────────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        return {
            "started_phases": list(self._started),
            "event_bus_transport": getattr(self.event_bus, "transport_mode", "none"),
        }
