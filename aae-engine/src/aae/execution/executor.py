from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

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

    The public ``sandbox`` attribute is the canonical execution target.
    Callers can override it at any time; the ``run`` method always consults
    ``self.sandbox`` for the actual execution call.
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
        # ``sandbox`` is the public, overridable execution target used by run().
        # If a raw sandbox (not a SandboxAdapter) is provided, keep it as-is so
        # that its sync execute() method is called directly.
        self.sandbox: Optional[Any] = sandbox
        # Also maintain a sandbox_adapter for callers that need the full adapter.
        self._sandbox_adapter: SandboxAdapter = (
            sandbox if isinstance(sandbox, SandboxAdapter) else SandboxAdapter()
        )

    def run(self, action: ActionSpec) -> ActionResult:
        """Execute an action with optional verification.

        Synchronous entry point.  Calls ``self.sandbox.execute(action)`` when a
        sandbox is set, otherwise falls back to local execution.
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
            if self.sandbox is not None:
                result = self.sandbox.execute(action)
            else:
                result = self._execute_local(action)
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
        """Execute locally without a sandbox (default fallback — always succeeds)."""
        return ActionResult(
            action_id=action.action_id,
            success=True,
            output="executed: %s" % action.action_type,
        )

    @property
    def sandbox_adapter(self) -> SandboxAdapter:
        """Get the sandbox adapter (for callers that need the async interface)."""
        return self._sandbox_adapter


__all__ = ["ActionResult", "ActionSpec", "ExecutionPolicy", "Executor"]
