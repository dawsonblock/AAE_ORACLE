from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional


class HealthChecker:
    """Aggregates health checks for all AAE subsystems.

    Each check returns a dict with at least ``status`` ("ok" | "degraded"
    | "down") and ``latency_ms``.  The overall system is "ok" only if
    every required check passes.
    """

    REQUIRED_CHECKS = {"postgres", "redis", "event_bus"}
    OPTIONAL_CHECKS = {"qdrant", "neo4j", "sandbox_docker"}

    def __init__(self) -> None:
        self._overrides: Dict[str, Dict[str, Any]] = {}

    # ── individual checks ─────────────────────────────────────────────────────

    def check_postgres(self) -> Dict[str, Any]:
        dsn = os.getenv("AAE_DATABASE_URL", "")
        if not dsn:
            return {"status": "degraded", "reason": "AAE_DATABASE_URL not set",
                    "latency_ms": 0}
        start = time.monotonic()
        try:
            import psycopg
            with psycopg.connect(dsn, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            return {"status": "ok", "latency_ms": _ms(start)}
        except Exception as exc:
            return {"status": "down", "reason": str(exc), "latency_ms": _ms(start)}

    def check_redis(self) -> Dict[str, Any]:
        url = os.getenv("REDIS_URL", "")
        if not url:
            return {"status": "degraded", "reason": "REDIS_URL not set",
                    "latency_ms": 0}
        start = time.monotonic()
        try:
            import redis
            r = redis.from_url(url, socket_connect_timeout=3)
            r.ping()
            return {"status": "ok", "latency_ms": _ms(start)}
        except Exception as exc:
            return {"status": "down", "reason": str(exc), "latency_ms": _ms(start)}

    def check_event_bus(self, transport_mode: str = "memory") -> Dict[str, Any]:
        return {"status": "ok", "transport": transport_mode, "latency_ms": 0}

    def check_qdrant(self) -> Dict[str, Any]:
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        start = time.monotonic()
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(url=url, timeout=3)
            client.get_collections()
            return {"status": "ok", "latency_ms": _ms(start)}
        except Exception as exc:
            return {"status": "down", "reason": str(exc), "latency_ms": _ms(start)}

    def check_neo4j(self) -> Dict[str, Any]:
        url = os.getenv("NEO4J_URL", "")
        if not url:
            return {"status": "degraded", "reason": "NEO4J_URL not set",
                    "latency_ms": 0}
        start = time.monotonic()
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                url,
                auth=(os.getenv("NEO4J_USER", "neo4j"),
                      os.getenv("NEO4J_PASSWORD", "")),
            )
            driver.verify_connectivity()
            driver.close()
            return {"status": "ok", "latency_ms": _ms(start)}
        except Exception as exc:
            return {"status": "down", "reason": str(exc), "latency_ms": _ms(start)}

    def check_sandbox_docker(self) -> Dict[str, Any]:
        start = time.monotonic()
        try:
            import docker
            client = docker.from_env(timeout=3)
            client.ping()
            return {"status": "ok", "latency_ms": _ms(start)}
        except Exception as exc:
            return {"status": "degraded", "reason": str(exc),
                    "latency_ms": _ms(start)}

    # ── aggregate ─────────────────────────────────────────────────────────────

    def run_all(
        self,
        transport_mode: str = "memory",
        include_optional: bool = True,
    ) -> Dict[str, Any]:
        checks: Dict[str, Dict[str, Any]] = {
            "postgres": self.check_postgres(),
            "redis": self.check_redis(),
            "event_bus": self.check_event_bus(transport_mode),
        }
        if include_optional:
            checks["qdrant"] = self.check_qdrant()
            checks["neo4j"] = self.check_neo4j()
            checks["sandbox_docker"] = self.check_sandbox_docker()

        required_ok = all(
            checks[k]["status"] == "ok"
            for k in self.REQUIRED_CHECKS
            if k in checks
        )
        overall = "ok" if required_ok else "degraded"
        # any required check "down" → system is down
        if any(
            checks[k]["status"] == "down"
            for k in self.REQUIRED_CHECKS
            if k in checks
        ):
            overall = "down"

        return {"status": overall, "checks": checks, "timestamp": time.time()}

    def liveness(self) -> Dict[str, Any]:
        """Minimal liveness probe — always returns ok if process is alive."""
        return {"status": "ok", "timestamp": time.time()}

    def readiness(self) -> Dict[str, Any]:
        """Readiness probe — checks required backends only."""
        result = self.run_all(include_optional=False)
        return result


def _ms(start: float) -> float:
    return round((time.monotonic() - start) * 1000, 2)
