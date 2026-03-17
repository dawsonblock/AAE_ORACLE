"""execution_logger — structured logging for every execution event.

Provides a queryable in-process log of all ExecRequests and ExecResults.
Designed to support the Monitoring subsystem and the Evaluation framework.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

log = logging.getLogger(__name__)


@dataclass
class ExecLogEntry:
    """Structured record of a single execution event."""

    task_id: str
    kind: str
    status: str
    exit_code: int = 0
    elapsed_ms: float = 0.0
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionLogger:
    """In-process ring buffer + optional JSONL file sink for exec events.

    Parameters
    ----------
    log_file:
        Optional path to a JSONL file.  If provided, every entry is
        appended so logs survive restarts.
    max_entries:
        Maximum entries kept in the ring buffer.
    """

    def __init__(
        self,
        log_file: Optional[Path] = None,
        max_entries: int = 10_000,
    ) -> None:
        self._log_file = log_file
        self._max = max_entries
        self._entries: List[ExecLogEntry] = []
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)

    # ── write ──────────────────────────────────────────────────────────────────

    def record(self, entry: ExecLogEntry) -> None:
        """Append an entry to the buffer and optional file sink."""
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max:]
        if self._log_file:
            self._append_file(entry)
        log.debug(
            "exec_log task_id=%s status=%s elapsed=%.1f",
            entry.task_id,
            entry.status,
            entry.elapsed_ms,
        )

    def record_dict(self, data: Dict[str, Any]) -> None:
        """Convenience: accept a plain dict and coerce it to ExecLogEntry."""
        self.record(
            ExecLogEntry(
                task_id=data.get("task_id", ""),
                kind=data.get("kind", "unknown"),
                status=data.get("status", "unknown"),
                exit_code=int(data.get("exit_code", 0)),
                elapsed_ms=float(data.get("elapsed_ms", 0.0)),
                error=data.get("error"),
                metadata=data.get("metadata", {}),
            )
        )

    # ── query ──────────────────────────────────────────────────────────────────

    def query(
        self,
        status: Optional[str] = None,
        kind: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> List[ExecLogEntry]:
        """Return entries matching all supplied filters, newest first."""
        results = list(reversed(self._entries))
        if status:
            results = [e for e in results if e.status == status]
        if kind:
            results = [e for e in results if e.kind == kind]
        if since is not None:
            results = [e for e in results if e.timestamp >= since]
        return results[:limit]

    def recent(self, n: int = 20) -> List[ExecLogEntry]:
        return list(reversed(self._entries))[:n]

    def error_rate(self, window: int = 100) -> float:
        """Return fraction of the last *window* entries that failed."""
        last = self._entries[-window:]
        if not last:
            return 0.0
        failed = sum(1 for e in last if e.status in ("failed", "timeout"))
        return failed / len(last)

    def stats(self) -> Dict[str, Any]:
        total = len(self._entries)
        by_status: Dict[str, int] = {}
        for e in self._entries:
            by_status[e.status] = by_status.get(e.status, 0) + 1
        return {"total": total, "by_status": by_status}

    # ── iteration ─────────────────────────────────────────────────────────────

    def __iter__(self) -> Iterator[ExecLogEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    # ── file sink ──────────────────────────────────────────────────────────────

    def _append_file(self, entry: ExecLogEntry) -> None:
        try:
            with self._log_file.open("a", encoding="utf-8") as fh:  # type: ignore[union-attr]
                fh.write(json.dumps(asdict(entry)) + "\n")
        except Exception as exc:
            log.warning("exec_logger file write failed: %s", exc)

    def load_from_file(self) -> int:
        """Replay entries from JSONL log file into the buffer."""
        if not self._log_file or not self._log_file.exists():
            return 0
        loaded = 0
        try:
            with self._log_file.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    self._entries.append(
                        ExecLogEntry(**{
                            k: v for k, v in data.items()
                            if k in ExecLogEntry.__dataclass_fields__
                        })
                    )
                    loaded += 1
        except Exception as exc:
            log.warning("exec_logger load failed: %s", exc)
        return loaded
