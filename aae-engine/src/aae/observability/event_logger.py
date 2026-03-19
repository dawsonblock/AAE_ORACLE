from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict


class EventLogger:
    def __init__(self, path: str = "logs/events.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: Dict[str, Any]) -> None:
        payload = {
            "timestamp": time.time(),
            **event,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")
