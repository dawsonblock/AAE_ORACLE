#!/usr/bin/env python3
"""scripts/run_sandbox_node.py — start a sandbox WorkerNode."""
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
log = logging.getLogger("run_sandbox_node")


async def _execute(task: dict) -> dict:
    """Sandbox task executor."""
    log.info("Sandbox executing task: %s", task.get("task_id"))
    from aae.execution.execution_manager import ExecutionManager, ExecRequest
    mgr = ExecutionManager()
    req = ExecRequest(
        task_id=task.get("task_id", "unknown"),
        kind=task.get("kind", "run_code"),
        payload=task.get("payload", {}),
    )
    result = await mgr.execute(req)
    return {"status": "ok", "exit_code": result.exit_code, "stdout": result.stdout}


async def main() -> None:
    queue_name = os.getenv("SANDBOX_QUEUE", "sandbox_tasks")
    concurrency = int(os.getenv("SANDBOX_CONCURRENCY", "2"))
    node = WorkerNode(
        node_id=f"sandbox-{os.getpid()}",
        queue_name=queue_name,
        execute_fn=_execute,
        concurrency=concurrency,
        worker_type="sandbox",
    )
    log.info(
        "Starting sandbox node (queue=%s, concurrency=%d)",
        queue_name,
        concurrency,
    )
    await node.start()
    log.info("Sandbox node stopped.")


if __name__ == "__main__":
    asyncio.run(main())
