"""resource_limiter — per-container resource enforcement for sandbox tasks.

Wraps Docker's resource constraint API and provides a higher-level
interface for setting and validating CPU, memory, disk, and network
limits on sandbox containers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class ResourceProfile:
    """Resource constraint spec for a single container."""

    cpu_quota: int = 50_000       # microseconds per 100 ms period (50% CPU)
    cpu_period: int = 100_000     # µs (default Docker period)
    memory_limit: str = "512m"    # e.g. "256m", "1g"
    memory_swap: str = "512m"     # swap = memory_limit → no swap
    pids_limit: int = 64          # max processes
    disk_bytes: int = 1_073_741_824  # 1 GiB
    network_disabled: bool = True
    read_only: bool = False

    def to_docker_params(self) -> Dict[str, Any]:
        """Translate to keyword args accepted by ``docker-py``'s ``run()``."""
        params: Dict[str, Any] = {
            "cpu_quota": self.cpu_quota,
            "cpu_period": self.cpu_period,
            "mem_limit": self.memory_limit,
            "memswap_limit": self.memory_swap,
            "pids_limit": self.pids_limit,
            "network_disabled": self.network_disabled,
            "read_only": self.read_only,
        }
        return params


class ResourceLimiter:
    """Apply and validate resource limits on sandbox containers.

    Parameters
    ----------
    default_profile:
        Profile used when no per-task override is supplied.
    strict:
        If ``True``, reject tasks that exceed max allowed limits.
    """

    # Absolute ceilings — no task may exceed these
    MAX_CPU_QUOTA = 80_000          # 80% of one core
    MAX_MEMORY = 2 * 1024 ** 3     # 2 GiB in bytes
    MAX_PIDS = 128

    def __init__(
        self,
        default_profile: Optional[ResourceProfile] = None,
        strict: bool = True,
    ) -> None:
        self.default = default_profile or ResourceProfile()
        self.strict = strict

    def resolve(
        self,
        override: Optional[ResourceProfile] = None,
    ) -> ResourceProfile:
        """Return *override* after clamping, or the default profile."""
        profile = override or self.default
        return self._clamp(profile)

    def validate(self, profile: ResourceProfile) -> bool:
        """Return ``True`` iff *profile* is within absolute ceilings."""
        if profile.cpu_quota > self.MAX_CPU_QUOTA:
            log.warning(
                "cpu_quota %d exceeds ceiling %d",
                profile.cpu_quota,
                self.MAX_CPU_QUOTA,
            )
            return not self.strict
        mem_bytes = self._parse_memory(profile.memory_limit)
        if mem_bytes > self.MAX_MEMORY:
            log.warning(
                "memory %s exceeds ceiling %d bytes",
                profile.memory_limit,
                self.MAX_MEMORY,
            )
            return not self.strict
        if profile.pids_limit > self.MAX_PIDS:
            log.warning(
                "pids_limit %d exceeds ceiling %d",
                profile.pids_limit,
                self.MAX_PIDS,
            )
            return not self.strict
        return True

    def apply_to_container(
        self,
        container: Any,
        profile: ResourceProfile,
    ) -> None:
        """Update a running Docker container's resource limits.

        ``container`` is a ``docker.models.containers.Container`` instance.
        """
        try:
            container.update(
                cpu_quota=profile.cpu_quota,
                cpu_period=profile.cpu_period,
                mem_limit=profile.memory_limit,
            )
            log.debug(
                "resource limits applied to container %s", container.id[:12]
            )
        except Exception as exc:
            log.error("failed to apply resource limits: %s", exc)

    # ── internal ──────────────────────────────────────────────────────────────

    def _clamp(self, profile: ResourceProfile) -> ResourceProfile:
        from dataclasses import replace
        return replace(
            profile,
            cpu_quota=min(profile.cpu_quota, self.MAX_CPU_QUOTA),
            pids_limit=min(profile.pids_limit, self.MAX_PIDS),
        )

    @staticmethod
    def _parse_memory(spec: str) -> int:
        """Parse Docker memory string to bytes (e.g. '512m' → 536870912)."""
        spec = spec.strip().lower()
        if spec.endswith("g"):
            return int(spec[:-1]) * 1024 ** 3
        if spec.endswith("m"):
            return int(spec[:-1]) * 1024 ** 2
        if spec.endswith("k"):
            return int(spec[:-1]) * 1024
        return int(spec)
