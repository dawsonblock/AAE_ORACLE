"""gateway/request_router — routes incoming API requests to AAE controller.

Acts as the seam between the public HTTP layer and the internal controller.
Translates HTTP-level DTOs into controller API calls and caches status.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class RequestRouter:
    """Route gateway requests to the workflow controller.

    Parameters
    ----------
    controller:
        The AAE ``WorkflowController`` (or ``ControllerRuntime``) instance.
    redis_store:
        Optional ``RedisStore`` for cross-replica status caching.
    """

    def __init__(
        self,
        controller: Any | None = None,
        redis_store: Any | None = None,
    ) -> None:
        self._ctrl = controller
        self._redis = redis_store
        # local status cache (workflow_id → status dict)
        self._cache: Dict[str, Dict[str, Any]] = {}
        # in-process route table for synchronous handler registration
        self._routes: Dict[str, Callable[..., Any]] = {}

    # ── synchronous routing (used by tests & lightweight callers) ───────────

    def register(self, path: str, handler: Callable[..., Any]) -> None:
        """Register *handler* for synchronous requests to *path*."""
        self._routes[path] = handler
        log.debug("RequestRouter registered path=%s", path)

    def route(
        self, path: str, data: Any = None
    ) -> Optional[Any]:
        """Dispatch a synchronous request to the registered handler.

        Returns ``None`` when no handler is registered for *path*.
        """
        handler = self._routes.get(path)
        if handler is None:
            log.debug("RequestRouter: no handler for path=%s", path)
            return None
        try:
            return handler(data)
        except Exception as exc:
            log.error("route handler error path=%s: %s", path, exc)
            return None

    # ── async workflow submission ──────────────────────────────────────────

    async def submit_workflow(
        self,
        goal: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Submit a new workflow and return its ID + initial status."""
        workflow_id = str(uuid.uuid4())
        submitted_at = time.time()
        status: Dict[str, Any] = {
            "workflow_id": workflow_id,
            "goal": goal,
            "status": "submitted",
            "submitted_at": submitted_at,
            "metadata": metadata or {},
        }
        self._cache[workflow_id] = status

        if self._redis:
            await self._redis.set(f"workflow:{workflow_id}", status, ttl=3600)

        if self._ctrl:
            try:
                await self._ctrl.submit(
                    workflow_id=workflow_id,
                    goal=goal,
                    metadata=metadata or {},
                )
                status["status"] = "running"
            except Exception as exc:
                log.error("controller submit failed: %s", exc)
                status["status"] = "failed"
                status["error"] = str(exc)

        self._cache[workflow_id] = status
        return {
            "workflow_id": workflow_id,
            "status": status["status"],
            "submitted_at": submitted_at,
        }

    async def get_workflow_status(
        self, workflow_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return the latest status for *workflow_id*, or None."""
        # Try controller first (source of truth)
        if self._ctrl and hasattr(self._ctrl, "get_status"):
            try:
                status = await self._ctrl.get_status(workflow_id)
                if status:
                    self._cache[workflow_id] = status
                    return status
            except Exception as exc:
                log.warning("controller get_status failed: %s", exc)

        # Try Redis cache
        if self._redis:
            cached = await self._redis.get(f"workflow:{workflow_id}")
            if cached:
                return cached

        # Local cache
        return self._cache.get(workflow_id)

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Request cancellation of *workflow_id*. Returns True if accepted."""
        if self._ctrl and hasattr(self._ctrl, "cancel"):
            try:
                await self._ctrl.cancel(workflow_id)
                if workflow_id in self._cache:
                    self._cache[workflow_id]["status"] = "cancelled"
                return True
            except Exception as exc:
                log.error("cancel workflow %s failed: %s", workflow_id, exc)
        return False

    async def list_workflows(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Return a list of recent workflow status summaries."""
        if self._ctrl and hasattr(self._ctrl, "list_workflows"):
            try:
                return await self._ctrl.list_workflows(limit=limit)
            except Exception:
                pass
        return list(self._cache.values())[-limit:]
