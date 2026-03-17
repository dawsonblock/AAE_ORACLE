#!/usr/bin/env python3
"""scripts/run_planner_node.py — start a planner WorkerNode."""
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
log = logging.getLogger("run_planner_node")


async def _execute(task: dict) -> dict:
    """Planner task executor — plug in real planner logic here."""
    log.info("Planner executing task: %s", task.get("task_id"))
    # TODO: delegate to PlannerAgent or BeamSearchPlanner
    return {"status": "ok", "plan": []}


async def main() -> None:
    queue_name = os.getenv("PLANNER_QUEUE", "planner_tasks")
    concurrency = int(os.getenv("PLANNER_CONCURRENCY", "2"))
    node = WorkerNode(
        node_id=f"planner-{os.getpid()}",
        queue_name=queue_name,
        execute_fn=_execute,
        concurrency=concurrency,
        worker_type="planner",
    )
    log.info("Starting planner node (queue=%s, concurrency=%d)", queue_name, concurrency)
    await node.start()
    log.info("Planner node stopped.")


if __name__ == "__main__":
    asyncio.run(main())
