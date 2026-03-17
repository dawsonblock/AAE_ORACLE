"""cluster/load_balancer — capacity-aware worker selection.

Provides a simple least-loaded selection strategy.  In a multi-replica
cluster the balancer checks queue depths and picks the worker type
(or node) with the most available capacity.
"""
from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class LoadBalancer:
    """Select worker queues based on observed queue depth.

    Parameters
    ----------
    queue_adapter:
        Used to query queue depths for balancing decisions.
    strategy:
        ``"least_loaded"`` (default) or ``"random"``.
    """

    def __init__(
        self,
        queue_adapter: Any | None = None,
        strategy: str = "least_loaded",
    ) -> None:
        self._queue = queue_adapter
        self.strategy = strategy
        # manual weight overrides: worker_type → weight multiplier
        self._weights: Dict[str, float] = {}

    async def select(self, preferred_type: str) -> str:
        """Return the best worker type for the next task.

        If the preferred type is healthy (depth < ceiling), return it
        directly.  Otherwise return the least-loaded alternative.
        """
        if self.strategy == "random":
            return random.choice(["planner", "agent", "sandbox"])

        depths = await self._depths()
        if not depths:
            return preferred_type

        ceiling = 100
        if depths.get(preferred_type, 0) < ceiling:
            return preferred_type

        # Pick least loaded that can handle the task
        candidates = sorted(depths.items(), key=lambda x: x[1])
        for wtype, depth in candidates:
            if depth < ceiling:
                log.debug(
                    "load_balance preferred=%s → selected=%s depth=%d",
                    preferred_type,
                    wtype,
                    depth,
                )
                return wtype
        return preferred_type

    def set_weight(self, worker_type: str, weight: float) -> None:
        self._weights[worker_type] = weight

    def pick(self, workers: List[str]) -> Optional[str]:
        """Synchronous selection from an explicit *workers* list.

        Uses the balancer's strategy.  Useful for in-process routing
        where no async queue-depth data is needed.
        """
        if not workers:
            return None
        if self.strategy == "random":
            return random.choice(workers)
        # round-robin via index
        idx = getattr(self, "_rr_idx", 0)
        result = workers[idx % len(workers)]
        self._rr_idx = idx + 1  # type: ignore[attr-defined]
        return result

    async def status(self) -> Dict[str, Any]:
        depths = await self._depths()
        return {
            "strategy": self.strategy,
            "queue_depths": depths,
            "weights": dict(self._weights),
        }

    async def _depths(self) -> Dict[str, int]:
        if self._queue:
            try:
                return await self._queue.all_depths()
            except Exception as exc:
                log.debug("load_balancer depth query failed: %s", exc)
        return {}


class RoundRobinBalancer(LoadBalancer):
    """Simple round-robin load balancer — no queue-depth queries required."""

    def __init__(
        self,
        worker_types: Optional[List[str]] = None,
    ) -> None:
        super().__init__(strategy="round_robin")
        self._types = worker_types or ["planner", "agent", "sandbox"]
        self._idx = 0

    async def select(self, preferred_type: str) -> str:
        result = self._types[self._idx % len(self._types)]
        self._idx += 1
        return result
