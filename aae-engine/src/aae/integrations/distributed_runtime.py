from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class RuntimeWorker:
    worker_id: str
    capability: str
    completed: int = 0
    busy: bool = False


class DistributedRuntime:
    def __init__(self) -> None:
        self.workers: List[RuntimeWorker] = [
            RuntimeWorker('worker-research-1', 'research'),
            RuntimeWorker('worker-security-1', 'security'),
            RuntimeWorker('worker-engineering-1', 'engineering'),
            RuntimeWorker('worker-general-1', 'general'),
        ]

    def pick(self, lane: str) -> RuntimeWorker:
        for worker in self.workers:
            if worker.capability == lane and not worker.busy:
                worker.busy = True
                return worker
        for worker in self.workers:
            if worker.capability == 'general' and not worker.busy:
                worker.busy = True
                return worker
        worker = self.workers[0]
        worker.busy = True
        return worker

    def complete(self, worker: RuntimeWorker) -> None:
        worker.busy = False
        worker.completed += 1

    def status(self) -> List[Dict[str, Any]]:
        return [worker.__dict__.copy() for worker in self.workers]
