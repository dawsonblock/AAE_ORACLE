from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """Abstract base class for all AAE micro-agents.

    Agents are stateless executors.  All state is passed in via ``task``
    and ``context``; results are returned as plain dicts.  Agents must
    never:
        - run shell commands directly (use execution_manager)
        - write to memory directly (use memory_manager)
        - modify task state (use the controller runtime)

    Subclasses implement ``run`` and may optionally override
    ``pre_run`` / ``post_run`` hooks for cross-cutting concerns.
    """

    name: str = "base"
    domain: str = "generic"

    @abstractmethod
    async def run(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the agent's primary logic.

        Args:
            task:    Task payload from the controller.
            context: Shared workflow context (repo path, memory, etc.)

        Returns:
            A result dict with at least ``{"status": "..."}`.
        """

    async def pre_run(
        self, task: Dict[str, Any], context: Dict[str, Any]
    ) -> None:
        """Optional hook called before ``run``."""

    async def post_run(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Optional hook called after ``run`` (even on failure)."""

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adapter called by the ControllerRuntime / ExecutionGuard."""
        task = payload.get("task", payload)
        context = payload.get("context", {})
        await self.pre_run(task, context)
        result = await self.run(task, context)
        await self.post_run(task, context, result)
        return result

    def describe(self) -> Dict[str, str]:
        return {"name": self.name, "domain": self.domain}
