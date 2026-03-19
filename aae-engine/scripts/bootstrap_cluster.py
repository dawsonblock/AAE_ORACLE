#!/usr/bin/env python3
"""scripts/bootstrap_cluster.py — idempotent cluster bootstrap.

Run once before starting any worker processes to ensure Postgres DDL,
Redis streams, Qdrant collections, and artifact directories exist.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure src/ is on the path when running directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aae.runtime.bootstrap import bootstrap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("bootstrap_cluster")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the AAE runtime environment.")
    parser.add_argument("--config", default=None, help="Reserved for compatibility with make bootstrap.")
    args = parser.parse_args()
    log.info("Starting cluster bootstrap …")
    result = bootstrap(config_path=args.config)
    if result.get("status") == "ok":
        log.info("Bootstrap completed successfully.")
        for check in result.get("checks", []):
            log.info("check=%s", check)
    else:
        log.error("Bootstrap encountered errors — check logs above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
