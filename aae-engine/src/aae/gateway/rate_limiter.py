"""gateway/rate_limiter — token-bucket rate limiter per API client.

Protects the gateway from runaway callers.  Each identity (API key hash
or JWT subject) has its own token bucket.  Requests consume one token;
buckets refill at a configurable rate.

The limiter is intentionally in-process (no Redis).  For multi-replica
deployments wrap it in a Redis-backed sliding window.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class Bucket:
    """Token-bucket state for a single client."""

    capacity: float
    refill_rate: float            # tokens per second
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def consume(self, amount: float = 1.0) -> bool:
        """Refill then attempt to consume *amount* tokens.

        Returns ``True`` if the request is allowed.
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate,
        )
        self.last_refill = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class RateLimiter:
    """Per-identity token-bucket rate limiter.

    Parameters
    ----------
    capacity:
        Maximum tokens per bucket (= burst allowance).
    refill_rate:
        Tokens added per second (= sustained request rate).
    max_buckets:
        Maximum number of tracked identities (LRU eviction after this).
    """

    def __init__(
        self,
        capacity: float = 60.0,
        refill_rate: float = 1.0,
        max_buckets: int = 10_000,
        # convenience aliases
        rate: Optional[float] = None,
        burst: Optional[float] = None,
    ) -> None:
        self.capacity = burst if burst is not None else capacity
        self.refill_rate = rate if rate is not None else refill_rate
        self.max_buckets = max_buckets
        self._buckets: Dict[str, Bucket] = {}
        self._access_order: list[str] = []

    def allow(self, identity: str, cost: float = 1.0) -> bool:
        """Return ``True`` if *identity* is within rate limit."""
        bucket = self._get_or_create(identity)
        allowed = bucket.consume(cost)
        if not allowed:
            log.warning("rate limit hit for identity=%s", identity[:16])
        return allowed

    def check(self, identity: str, cost: float = 1.0) -> bool:
        """Alias for :meth:`allow`."""
        return self.allow(identity, cost)

    def remaining(self, identity: str) -> float:
        """Return approximate remaining tokens for *identity*."""
        bucket = self._buckets.get(identity)
        if not bucket:
            return self.capacity
        # Simulate refill without consuming
        now = time.monotonic()
        elapsed = now - bucket.last_refill
        return min(
            self.capacity,
            bucket.tokens + elapsed * self.refill_rate,
        )

    def reset(self, identity: Optional[str] = None) -> None:
        """Reset all buckets (or just *identity* if given)."""
        if identity:
            self._buckets.pop(identity, None)
        else:
            self._buckets.clear()
            self._access_order.clear()

    def stats(self) -> Dict[str, int]:
        return {
            "tracked_identities": len(self._buckets),
            "capacity": int(self.capacity),
            "refill_rate": int(self.refill_rate),
        }

    # ── internal ──────────────────────────────────────────────────────────────

    def _get_or_create(self, identity: str) -> Bucket:
        if identity not in self._buckets:
            if len(self._buckets) >= self.max_buckets:
                oldest = self._access_order.pop(0)
                self._buckets.pop(oldest, None)
            bucket = Bucket(
                capacity=self.capacity,
                refill_rate=self.refill_rate,
                tokens=self.capacity,
            )
            self._buckets[identity] = bucket
            self._access_order.append(identity)
        return self._buckets[identity]
