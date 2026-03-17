from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List


def bootstrap(config_path: str | None = None) -> Dict[str, Any]:
    """One-shot bootstrap: ensure directories, DB tables, and env are ready.

    Safe to run multiple times (idempotent).  Intended to be called via
    ``make bootstrap`` or ``scripts/bootstrap_cluster.py`` before any
    worker is started.
    """
    results: List[str] = []

    # 1. Artifact directories
    _ensure_dirs([".artifacts", ".artifacts/events", ".artifacts/traces",
                  ".artifacts/patches", ".artifacts/meta", "datasets"])
    results.append("artifact_dirs_ok")

    # 2. PostgreSQL tables
    dsn = os.getenv("AAE_DATABASE_URL", "")
    if dsn:
        try:
            _bootstrap_postgres(dsn)
            results.append("postgres_ok")
        except Exception as exc:
            results.append("postgres_skip: %s" % exc)
    else:
        results.append("postgres_skip: AAE_DATABASE_URL not set")

    # 3. Redis connectivity check
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            _check_redis(redis_url)
            results.append("redis_ok")
        except Exception as exc:
            results.append("redis_skip: %s" % exc)
    else:
        results.append("redis_skip: REDIS_URL not set")

    # 4. Python path — ensure src/ is importable
    src = str(Path(__file__).resolve().parents[3])
    if src not in sys.path:
        sys.path.insert(0, src)
    results.append("python_path_ok")

    return {"status": "ok", "checks": results}


# ── internal helpers ──────────────────────────────────────────────────────────

def _ensure_dirs(paths: List[str]) -> None:
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)


def _bootstrap_postgres(dsn: str) -> None:
    import psycopg
    ddl_statements = [
        """CREATE TABLE IF NOT EXISTS aae_checkpoints (
               id         TEXT             PRIMARY KEY,
               state      JSONB            NOT NULL DEFAULT '{}',
               updated_at DOUBLE PRECISION NOT NULL DEFAULT 0
           )""",
        """CREATE TABLE IF NOT EXISTS aae_events (
               id          TEXT             PRIMARY KEY,
               event_type  TEXT             NOT NULL,
               workflow_id TEXT,
               source      TEXT,
               payload     JSONB,
               created_at  DOUBLE PRECISION NOT NULL
           )""",
        "CREATE INDEX IF NOT EXISTS idx_aae_events_wf "
        "ON aae_events (workflow_id)",
        "CREATE INDEX IF NOT EXISTS idx_aae_events_type "
        "ON aae_events (event_type)",
        """CREATE TABLE IF NOT EXISTS aae_trajectories (
               id          TEXT             PRIMARY KEY,
               task_type   TEXT,
               agent_type  TEXT,
               tool_used   TEXT,
               success     BOOLEAN,
               duration_s  DOUBLE PRECISION,
               token_cost  INTEGER,
               payload     JSONB,
               created_at  DOUBLE PRECISION NOT NULL
           )""",
    ]
    with psycopg.connect(dsn) as conn:
        for ddl in ddl_statements:
            conn.execute(ddl)
        conn.commit()


def _check_redis(redis_url: str) -> None:
    import redis as redis_lib
    r = redis_lib.from_url(redis_url, socket_connect_timeout=3)
    r.ping()
