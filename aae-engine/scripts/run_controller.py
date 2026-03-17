#!/usr/bin/env python3
"""scripts/run_controller.py — start the deterministic ControllerRuntime."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aae.controller.controller_runtime import ControllerRuntime

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("run_controller")


async def main() -> None:
    log.info("Initialising ControllerRuntime …")
    controller = ControllerRuntime()
    await controller.start()
    log.info("ControllerRuntime running. Press Ctrl+C to stop.")

    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)

    await stop
    log.info("Shutdown signal received — stopping controller …")
    await controller.stop()
    log.info("Controller stopped.")


if __name__ == "__main__":
    asyncio.run(main())
