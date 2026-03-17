from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict

from aae.core.event_log import EventLog
from aae.execution.sandbox_adapter import SandboxAdapter


@dataclass
class ActionSpec:
    action_id: str
    action_type: str
    command: str | None = None
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    action_id: str
    success: bool
    output: str = ""
    error: str = ""
    artifacts: Dict[str, Any] = field(default_factory=dict)


class ExecutionPolicy:
    def validate(self, action: ActionSpec) -> bool:
        if not action.action_id:
            return False
        if not action.action_type:
            return False
        return True


class Executor:
    """Executor that orchestrates execution + verification.

    Uses SandboxAdapter as the ONLY way to access the sandbox for execution.
    """

    def __init__(
        self,
        policy: ExecutionPolicy | None = None,
        sandbox: Any | None = None,
        verifier: Any | None = None,
        event_log: EventLog | None = None,
    ) -> None:
        self.policy = policy or ExecutionPolicy()
        self.verifier = verifier
        self.event_log = event_log or EventLog()
        # Use sandbox_adapter if provided, otherwise wrap sandbox or create default
        if sandbox is not None:
            if isinstance(sandbox, SandboxAdapter):
                self._sandbox_adapter = sandbox
            else:
                # Wrap raw sandbox in adapter
                self._sandbox_adapter = SandboxAdapter(sandbox)
        else:
            # Create default adapter
            self._sandbox_adapter = SandboxAdapter()

    async def run(self, action: ActionSpec) -> ActionResult:
        """Execute an action with verification.

        Args:
            action: The ActionSpec to execute

        Returns:
            ActionResult with execution outcome and verification status
        """
        self.event_log.create_event(
            event_type="action_started",
            task_id=action.action_id,
            action=action.action_type,
            status="started",
        )

        if not self.policy.validate(action):
            self.event_log.create_event(
                event_type="action_rejected",
                task_id=action.action_id,
                action=action.action_type,
                status="rejected",
                payload={"reason": "policy_validation_failed"},
            )
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error="action rejected by execution policy",
            )

        try:
            # Execute via sandbox adapter (async)
            result = await self._sandbox_adapter.execute(action)
        except Exception as exc:
            self.event_log.create_event(
                event_type="action_failed",
                task_id=action.action_id,
                action=action.action_type,
                status="error",
                payload={"error": str(exc)},
            )
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=str(exc),
            )

        if self.verifier is not None:
            verified = self.verifier.verify(action, result)
            if not verified.success:
                self.event_log.create_event(
                    event_type="verification_failed",
                    task_id=action.action_id,
                    action=action.action_type,
                    status="verification_failed",
                )
                return verified

        self.event_log.create_event(
            event_type="action_completed",
            task_id=action.action_id,
            action=action.action_type,
            status="success",
        )
        return result

    def _execute_local(self, action: ActionSpec) -> ActionResult:
        """Execute locally without sandbox (fallback)."""
        return ActionResult(
            action_id=action.action_id,
            success=True,
            output="executed: %s" % action.action_type,
        )

    @property
    def sandbox_adapter(self) -> SandboxAdapter:
        """Get the sandbox adapter."""
        return self._sandbox_adapter


__all__ = ["ActionResult", "ActionSpec", "ExecutionPolicy", "Executor"]
