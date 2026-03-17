#!/usr/bin/env python3
"""scripts/bootstrap_cluster.py — idempotent cluster bootstrap.

Run once before starting any worker processes to ensure Postgres DDL,
Redis streams, Qdrant collections, and artifact directories exist.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure src/ is on the path when running directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aae.runtime.bootstrap import Bootstrap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("bootstrap_cluster")


async def main() -> None:
    log.info("Starting cluster bootstrap …")
    b = Bootstrap()
    ok = await b.run()
    if ok:
        log.info("Bootstrap completed successfully.")
    else:
        log.error("Bootstrap encountered errors — check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
