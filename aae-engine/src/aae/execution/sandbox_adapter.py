import subprocess
from .patch_engine import PatchEngine


class SandboxAdapter:
    def __init__(self):
        self.patch_engine = PatchEngine()

    def run(self, command):
        ctype = command["type"]

        if ctype == "patch":
            return self.patch_engine.apply_patch(
                command["repo"], command["patch"]
            )

        if ctype == "test":
            proc = subprocess.run(
                command.get("cmd", "pytest -q"),
                cwd=command["repo"],
                shell=True,
                capture_output=True,
                text=True
            )
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
            }

        if ctype == "shell":
            proc = subprocess.run(
                command["cmd"],
                cwd=command["repo"],
                shell=True,
                capture_output=True,
                text=True
            )
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
            }

        return {"exit_code": 1, "stderr": f"unknown command type: {ctype}"}
"""Sandbox adapter module - wraps real sandbox for execution.

This adapter provides the interface between the Executor and the real
SandboxManager. It follows the adapter pattern to translate ActionSpec
calls into SandboxManager commands.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aae.execution.executor import ActionResult, ActionSpec

if TYPE_CHECKING:
    from aae.sandbox.sandbox_manager import SandboxManager


class SandboxAdapter:
    """Adapter that wraps the real SandboxManager for use by the Executor.

    This is the ONLY way execution should access the sandbox - all sandbox
    interactions go through this adapter to ensure consistent interface
    and proper result translation.
    """

    def __init__(
        self,
        sandbox_manager: "SandboxManager | None" = None,
    ) -> None:
        """Initialize adapter with optional sandbox manager.

        Args:
            sandbox_manager: Optional SandboxManager instance. If not provided,
                           a new SandboxManager will be created.
        """
        if sandbox_manager is not None:
            self._sandbox = sandbox_manager
        else:
            from aae.sandbox.sandbox_manager import SandboxManager
            self._sandbox = SandboxManager()

    async def execute(self, action: ActionSpec) -> ActionResult:
        """Execute an action in the sandbox.

        Translates ActionSpec to sandbox command and returns standardized
        ActionResult.

        Args:
            action: The ActionSpec to execute

        Returns:
            ActionResult with execution outcome
        """
        # Extract command from action - prefer field, fall back to payload
        command = action.command
        if not command:
            command = action.payload.get("command", "")

        # Extract workdir from payload, default to current directory
        workdir = action.payload.get("workdir", ".")

        if not command:
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error="No command provided in action",
            )

        try:
            # Execute via the real sandbox manager
            result = await self._sandbox.run_job(
                command=command,
                workdir=workdir,
            )

            # Translate sandbox result to ActionResult
            return ActionResult(
                action_id=action.action_id,
                success=result.get("returncode", 1) == 0,
                output=result.get("stdout", ""),
                error=result.get("stderr", ""),
                artifacts={
                    "container_id": result.get("container_id"),
                    "returncode": result.get("returncode"),
                    "execution_mode": result.get("execution_mode"),
                    "trust_level": result.get("trust_level"),
                    "fallback_reason": result.get("fallback_reason"),
                    "artifact_paths": result.get("artifact_paths", []),
                    "trace_paths": result.get("trace_paths", []),
                    "coverage_path": result.get("coverage_path"),
                    "applied_workspace": result.get("applied_workspace"),
                    "editable_workspace": result.get("editable_workspace"),
                    "rollback_status": result.get("rollback_status"),
                    "patch_apply_status": result.get("patch_apply_status"),
                    "patch_apply_details": result.get("patch_apply_details"),
                    "counterexample_paths": result.get("counterexample_paths", []),
                },
            )
        except Exception as exc:
            return ActionResult(
                action_id=action.action_id,
                success=False,
                error=str(exc),
            )

    async def execute_spec(self, spec: Any) -> Any:
        """Execute a SandboxRunSpec directly.

        Allows direct access to sandbox specification execution when needed.

        Args:
            spec: SandboxRunSpec to execute

        Returns:
            Raw sandbox result
        """
        return await self._sandbox.execute_spec(spec)

    def get_sandbox(self) -> "SandboxManager":
        """Get the underlying sandbox manager.

        Returns:
            The wrapped SandboxManager instance
        """
        return self._sandbox


__all__ = ["SandboxAdapter"]
