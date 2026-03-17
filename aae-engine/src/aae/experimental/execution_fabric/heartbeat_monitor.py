"""execution_fabric/heartbeat_monitor — tracks node liveness.

Workers send heartbeats periodically.  The monitor marks nodes as dead
when they miss too many heartbeats and notifies the WorkerManager so
replacement workers can be spawned.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Dict, List, Optional

log = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0   # seconds without heartbeat → dead
_CHECK_INTERVAL = 10.0    # seconds between liveness sweeps


class HeartbeatMonitor:
    """Monitor node heartbeats and trigger callbacks on failure.

    Parameters
    ----------
    timeout:
        Seconds after which a node is considered dead.
    on_dead:
        Async callback invoked with ``(node_id: str)`` when a node dies.
    """

    def __init__(
        self,
        timeout: float = _DEFAULT_TIMEOUT,
        on_dead: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._timeout = timeout
        self._on_dead = on_dead
        self._last_seen: Dict[str, float] = {}
        self._task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        self._task = asyncio.create_task(
            self._check_loop(), name="heartbeat-monitor"
        )
        log.info("HeartbeatMonitor started (timeout=%ds)", int(self._timeout))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def beat(self, node_id: str) -> None:
        """Record a heartbeat from *node_id*."""
        self._last_seen[node_id] = time.monotonic()

    def register(self, node_id: str) -> None:
        """Register a new node (same as beat for initial registration)."""
        self.beat(node_id)

    def deregister(self, node_id: str) -> None:
        self._last_seen.pop(node_id, None)

    def unhealthy(self) -> List[str]:
        """Return IDs of nodes that have missed their heartbeat deadline."""
        cutoff = time.monotonic() - self._timeout
        return [nid for nid, ts in self._last_seen.items() if ts < cutoff]

    def all_nodes(self) -> Dict[str, float]:
        """Return ``{node_id: last_seen_ago_seconds}`` for all nodes."""
        now = time.monotonic()
        return {nid: now - ts for nid, ts in self._last_seen.items()}

    async def _check_loop(self) -> None:
        while True:
            await asyncio.sleep(_CHECK_INTERVAL)
            dead = self.unhealthy()
            for nid in dead:
                log.warning("node %s missed heartbeat, marking dead", nid[:8])
                if self._on_dead:
                    try:
                        if asyncio.iscoroutinefunction(self._on_dead):
                            await self._on_dead(nid)
                        else:
                            self._on_dead(nid)
                    except Exception as exc:
                        log.error("on_dead callback failed: %s", exc)
                self._last_seen.pop(nid, None)
