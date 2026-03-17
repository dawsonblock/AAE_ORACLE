#!/usr/bin/env python3
"""scripts/run_learning_pipeline.py — run one learning + meta-improvement cycle."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
log = logging.getLogger("run_learning_pipeline")


async def main() -> None:
    epochs = int(os.getenv("LEARNING_EPOCHS", "3"))
    batch_size = int(os.getenv("LEARNING_BATCH_SIZE", "32"))
    model_path = os.getenv("MODEL_PATH", "models/policy.pt")

    log.info(
        "Starting learning pipeline (epochs=%d, batch_size=%d, model=%s)",
        epochs,
        batch_size,
        model_path,
    )

    try:
        from aae.learning.trajectory_loader import TrajectoryLoader
        loader = TrajectoryLoader()
        trajectories = await loader.load_all()
        log.info("Loaded %d trajectories.", len(trajectories))
    except ImportError:
        log.warning("aae.learning.trajectory_loader unavailable — skipping load.")
        trajectories = []

    try:
        from aae.learning.trainer import Trainer
        trainer = Trainer(epochs=epochs, batch_size=batch_size, model_path=model_path)
        metrics = await trainer.train(trajectories)
        log.info("Training complete: %s", metrics)
    except ImportError:
        log.warning("aae.learning.trainer unavailable — skipping training.")

    try:
        from aae.learning.meta_updater import MetaUpdater
        updater = MetaUpdater()
        await updater.update_configs()
        log.info("Meta-config updated.")
    except ImportError:
        log.warning("aae.learning.meta_updater unavailable — skipping meta-update.")

    log.info("Learning pipeline finished.")


if __name__ == "__main__":
    asyncio.run(main())
