"""cleanup_service — background service that garbage-collects old sandboxes.

Runs as a periodic async task.  Scans the container pool and artifact
directories for stale entries and removes them, preventing disk and
container leakage in long-running deployments.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_DEFAULT_INTERVAL = 300        # seconds between cleanup sweeps
_DEFAULT_CONTAINER_TTL = 600   # seconds before idle container is killed
_DEFAULT_ARTIFACT_TTL = 86400  # seconds before artifact is deleted


class CleanupService:
    """Periodic garbage collector for sandbox containers and artefacts.

    Parameters
    ----------
    sandbox_manager:
        Reference to the ``SandboxManager`` to query/kill containers.
    artifact_root:
        Root directory of the artefact store.
    interval:
        Seconds between cleanup sweeps.
    container_ttl:
        Kill containers idle longer than this many seconds.
    artifact_ttl:
        Delete artefact files older than this many seconds.
    """

    def __init__(
        self,
        sandbox_manager: Any | None = None,
        artifact_root: Optional[Path] = None,
        interval: float = _DEFAULT_INTERVAL,
        container_ttl: float = _DEFAULT_CONTAINER_TTL,
        artifact_ttl: float = _DEFAULT_ARTIFACT_TTL,
    ) -> None:
        self._sandbox = sandbox_manager
        self._artifacts = artifact_root or Path(".artifacts")
        self.interval = interval
        self.container_ttl = container_ttl
        self.artifact_ttl = artifact_ttl
        self._task: Optional[asyncio.Task[None]] = None
        self._stats: Dict[str, int] = {
            "containers_killed": 0,
            "artifacts_deleted": 0,
            "sweeps": 0,
        }

    async def start(self) -> None:
        """Start the background cleanup loop."""
        self._task = asyncio.create_task(self._loop(), name="cleanup-service")
        log.info("cleanup_service started (interval=%ds)", int(self.interval))

    async def stop(self) -> None:
        """Cancel the background loop and wait for it to finish."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("cleanup_service stopped")

    async def sweep(self) -> Dict[str, int]:
        """Perform a single cleanup sweep and return counts."""
        c_killed = await self._cleanup_containers()
        a_deleted = self._cleanup_artifacts()
        self._stats["containers_killed"] += c_killed
        self._stats["artifacts_deleted"] += a_deleted
        self._stats["sweeps"] += 1
        log.info(
            "cleanup sweep: containers_killed=%d artifacts_deleted=%d",
            c_killed,
            a_deleted,
        )
        return {"containers_killed": c_killed, "artifacts_deleted": a_deleted}

    def stats(self) -> Dict[str, int]:
        return dict(self._stats)

    # ── internal ──────────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval)
            try:
                await self.sweep()
            except Exception as exc:
                log.error("cleanup sweep error: %s", exc)

    async def _cleanup_containers(self) -> int:
        if not self._sandbox:
            return 0
        killed = 0
        try:
            idle: List[Any] = await self._sandbox.list_idle(
                older_than=self.container_ttl
            )
            for container in idle:
                try:
                    await self._sandbox.kill(container)
                    killed += 1
                except Exception as exc:
                    log.warning("failed to kill container: %s", exc)
        except Exception as exc:
            log.warning("list_idle failed: %s", exc)
        return killed

    def _cleanup_artifacts(self) -> int:
        deleted = 0
        cutoff = time.time() - self.artifact_ttl
        for path in self._artifacts.rglob("*"):
            if not path.is_file():
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    deleted += 1
            except Exception as exc:
                log.debug("artifact delete failed %s: %s", path, exc)
        return deleted
