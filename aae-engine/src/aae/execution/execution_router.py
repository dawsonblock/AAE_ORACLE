"""execution_router — maps task types to ExecutionManager strategies.

Agents submit high-level action requests (e.g. "validate patch",
"run regression suite").  This router translates them into concrete
``ExecRequest`` objects and dispatches them to the ``ExecutionManager``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .execution_manager import ExecRequest, ExecResult, ExecutionManager

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Route table
# ---------------------------------------------------------------------------

_ROUTE_TABLE: Dict[str, str] = {
    # agent action → ExecRequest kind
    "run_tests": "test",
    "validate_patch": "test",
    "regression_suite": "test",
    "execute_script": "script",
    "run_command": "command",
    "eval_code": "code",
    "run_code": "code",
    "sandbox_exec": "command",
}


class ExecutionRouter:
    """Translate agent actions into ExecRequests and dispatch them.

    Parameters
    ----------
    manager:
        The ``ExecutionManager`` to delegate to.
    """

    def __init__(self, manager: Optional[ExecutionManager] = None) -> None:
        self._mgr = manager or ExecutionManager()

    async def route(
        self,
        action: str,
        payload: Dict[str, Any],
        timeout: float = 120.0,
        isolation: bool = True,
    ) -> ExecResult:
        """Route *action* → ExecRequest → ExecResult.

        Unknown actions default to a dry-run command execution.
        """
        kind = _ROUTE_TABLE.get(action, "command")
        request = ExecRequest(
            kind=kind,
            payload=payload,
            isolation=isolation,
            timeout=timeout,
        )
        log.debug("routing action=%s as kind=%s", action, kind)
        return await self._mgr.execute(request)

    async def run_tests(
        self,
        test_ids: List[str],
        timeout: float = 180.0,
        isolation: bool = True,
    ) -> ExecResult:
        """Convenience wrapper: run a list of pytest test IDs."""
        return await self.route(
            "run_tests",
            {"test_ids": test_ids},
            timeout=timeout,
            isolation=isolation,
        )

    async def run_code(
        self,
        code: str,
        language: str = "python",
        timeout: float = 30.0,
    ) -> ExecResult:
        """Convenience wrapper: execute an inline code snippet."""
        return await self.route(
            "run_code",
            {"code": code, "language": language},
            timeout=timeout,
        )

    async def run_command(
        self,
        command: str,
        timeout: float = 60.0,
        isolation: bool = True,
    ) -> ExecResult:
        """Convenience wrapper: run an arbitrary shell command."""
        return await self.route(
            "run_command",
            {"command": command},
            timeout=timeout,
            isolation=isolation,
        )

    def stats(self) -> Dict[str, Any]:
        return self._mgr.stats()
