"""Tool router — dispatches agent tool calls to the correct backend.

Agents declare which tools they need (see ``BaseAgent.capabilities``).
Rather than invoking shell commands, subprocesses, or external APIs
directly, agents call ``ToolRouter.invoke(tool, payload)``.  The router
resolves the correct backend, enforces policy, logs the invocation, and
returns a normalised result dict.

Backends:
  - execution  : ExecutionManager for code/test runs
  - sandbox    : SandboxManager for isolated container runs
  - memory     : MemoryManager for read/write to L1-L4 memory
  - search     : Vector or keyword search against RIS index
  - external   : HTTP call to AgentField sibling APIs
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

# Tools that are always allowed regardless of capability list
_ALWAYS_ALLOWED: frozenset[str] = frozenset(
    {"memory_read", "memory_write", "search", "log"}
)

# Tools that require explicit capability declaration
_GATED: frozenset[str] = frozenset(
    {"run_tests", "run_code", "sandbox_exec", "external_call"}
)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


class ToolResult:
    """Normalised result from a tool invocation."""

    def __init__(
        self,
        tool: str,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
        elapsed_ms: float = 0.0,
    ) -> None:
        self.tool = tool
        self.success = success
        self.data = data
        self.error = error
        self.elapsed_ms = elapsed_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
        }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class ToolRouter:
    """Routes tool calls from agents to authorised backends.

    Parameters
    ----------
    capabilities:
        Set of tool names the agent is allowed to call.  Any call to a
        gated tool not in this set is immediately rejected.
    execution_manager:
        Optional ``ExecutionManager`` instance.
    sandbox_manager:
        Optional ``SandboxManager`` instance.
    memory_manager:
        Optional ``MemoryManager`` instance.
    """

    def __init__(
        self,
        capabilities: List[str] | None = None,
        execution_manager: Any | None = None,
        sandbox_manager: Any | None = None,
        memory_manager: Any | None = None,
    ) -> None:
        self.capabilities: frozenset[str] = frozenset(capabilities or [])
        self._exec = execution_manager
        self._sandbox = sandbox_manager
        self._memory = memory_manager
        self._registry: Dict[str, Callable[..., Any]] = {}
        self._build_registry()

    def _build_registry(self) -> None:
        self._registry = {
            "run_tests": self._run_tests,
            "run_code": self._run_code,
            "sandbox_exec": self._sandbox_exec,
            "memory_read": self._memory_read,
            "memory_write": self._memory_write,
            "search": self._search,
            "log": self._log_tool,
        }

    # ── public API ────────────────────────────────────────────────────────────

    async def invoke(
        self, tool: str, payload: Dict[str, Any]
    ) -> ToolResult:
        """Invoke *tool* with *payload*, enforcing policy."""
        t0 = time.perf_counter()

        # Policy check
        if tool in _GATED and tool not in self.capabilities:
            return ToolResult(
                tool=tool,
                success=False,
                error=f"Tool '{tool}' not in agent capability list.",
            )

        handler = self._registry.get(tool)
        if handler is None:
            return ToolResult(
                tool=tool,
                success=False,
                error=f"Unknown tool '{tool}'.",
            )

        try:
            data = await handler(payload)
            elapsed = (time.perf_counter() - t0) * 1000
            log.debug("tool=%s elapsed=%.1f ms", tool, elapsed)
            return ToolResult(
                tool=tool,
                success=True,
                data=data,
                elapsed_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            log.error("tool=%s error=%s", tool, exc)
            return ToolResult(
                tool=tool,
                success=False,
                error=str(exc),
                elapsed_ms=elapsed,
            )

    def available(self) -> List[str]:
        """Return list of tools available to this router instance."""
        return [
            t
            for t in self._registry
            if t in _ALWAYS_ALLOWED or t in self.capabilities
        ]

    # ── backend handlers ─────────────────────────────────────────────────────

    async def _run_tests(self, payload: Dict[str, Any]) -> Any:
        if self._sandbox:
            result = await self._sandbox.run_tests(
                test_ids=payload.get("test_ids", []),
                working_dir=payload.get("working_dir", "/workspace"),
            )
            return result
        # Fallback: return stub
        await asyncio.sleep(0)
        return {"status": "no_sandbox", "passed": 0, "failed": 0}

    async def _run_code(self, payload: Dict[str, Any]) -> Any:
        if self._exec:
            return await self._exec.execute(
                code=payload.get("code", ""),
                language=payload.get("language", "python"),
            )
        await asyncio.sleep(0)
        return {"stdout": "", "stderr": "no execution backend", "exit_code": 1}

    async def _sandbox_exec(self, payload: Dict[str, Any]) -> Any:
        if self._sandbox:
            return await self._sandbox.execute(
                command=payload.get("command", ""),
                image=payload.get("image", "python:3.11-slim"),
            )
        await asyncio.sleep(0)
        return {"stdout": "", "stderr": "no sandbox backend", "exit_code": 1}

    async def _memory_read(self, payload: Dict[str, Any]) -> Any:
        if self._memory:
            query = payload.get("query", "")
            k = int(payload.get("k", 5))
            results = await self._memory.search(query=query, k=k)
            return results
        await asyncio.sleep(0)
        return []

    async def _memory_write(self, payload: Dict[str, Any]) -> Any:
        if self._memory:
            await self._memory.store(
                key=payload.get("key", ""),
                value=payload.get("value"),
                metadata=payload.get("metadata", {}),
            )
            return {"stored": True}
        await asyncio.sleep(0)
        return {"stored": False}

    async def _search(self, payload: Dict[str, Any]) -> Any:
        query = payload.get("query", "")
        k = int(payload.get("k", 10))
        if self._memory:
            return await self._memory.search(query=query, k=k)
        await asyncio.sleep(0)
        return []

    async def _log_tool(self, payload: Dict[str, Any]) -> Any:
        log.info("[agent-log] %s", payload.get("message", ""))
        return {"logged": True}
