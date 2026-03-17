#!/usr/bin/env python3
"""scripts/run_agent_worker.py — start an agent WorkerNode."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aae.cluster.worker_node import WorkerNode

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("run_agent_worker")

_AGENT_TYPE = os.getenv("AGENT_TYPE", "engineering")


async def _execute(task: dict) -> dict:
    """Agent task executor — route to appropriate agent."""
    log.info("Agent (%s) executing task: %s", _AGENT_TYPE, task.get("task_id"))
    # TODO: dispatch to EngineeringAgent / SecurityAgent / TestAgent etc.
    return {"status": "ok", "agent_type": _AGENT_TYPE}


async def main() -> None:
    queue_name = os.getenv("AGENT_QUEUE", f"agent_{_AGENT_TYPE}")
    concurrency = int(os.getenv("AGENT_CONCURRENCY", "1"))
    node = WorkerNode(
        node_id=f"agent-{_AGENT_TYPE}-{os.getpid()}",
        queue_name=queue_name,
        execute_fn=_execute,
        concurrency=concurrency,
        worker_type="agent",
    )
    log.info(
        "Starting agent worker (type=%s, queue=%s, concurrency=%d)",
        _AGENT_TYPE,
        queue_name,
        concurrency,
    )
    await node.start()
    log.info("Agent worker stopped.")


if __name__ == "__main__":
    asyncio.run(main())
