"""artifact_writer — persists execution artefacts to the local filesystem.

Execution results (test outputs, generated patches, coverage reports, diff
files) are written here so that downstream agents can inspect them and so
they survive across restarts.

Directory layout::

    .artifacts/
    ├── patches/       ← generated diff files
    ├── test_results/  ← pytest JSON reports
    ├── coverage/      ← coverage.json / .xml
    ├── sandbox/       ← raw container stdout/stderr
    └── generic/       ← everything else
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_ROOT = Path(".artifacts")
_SUBDIRS = ["patches", "test_results", "coverage", "sandbox", "generic"]


class ArtifactWriter:
    """Write, read, and list execution artefacts.

    Parameters
    ----------
    root:
        Base directory.  Defaults to ``.artifacts`` in the CWD.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self._root = Path(root) if root else _ROOT
        self._ensure_dirs()

    # ── write ─────────────────────────────────────────────────────────────────

    def write_text(
        self,
        content: str,
        category: str = "generic",
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Write a plain-text artefact, return its path."""
        dest = self._resolve(category, filename or f"{uuid.uuid4()}.txt")
        dest.write_text(content, encoding="utf-8")
        self._write_meta(dest, metadata)
        log.debug("artifact written: %s", dest)
        return dest

    def write_json(
        self,
        data: Any,
        category: str = "generic",
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """Serialise *data* to JSON and write as an artefact."""
        dest = self._resolve(category, filename or f"{uuid.uuid4()}.json")
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._write_meta(dest, metadata)
        log.debug("artifact written: %s", dest)
        return dest

    def write_patch(
        self,
        diff: str,
        task_id: str | None = None,
    ) -> Path:
        """Write a unified diff artefact under ``patches/``."""
        name = f"{task_id or uuid.uuid4()}.patch"
        return self.write_text(diff, category="patches", filename=name)

    def write_test_result(
        self,
        result: Dict[str, Any],
        task_id: str | None = None,
    ) -> Path:
        """Write a test result dict under ``test_results/``."""
        name = f"{task_id or uuid.uuid4()}_result.json"
        return self.write_json(
            result, category="test_results", filename=name
        )

    # ── read ──────────────────────────────────────────────────────────────────

    def read(self, path: Path | str) -> str:
        """Read a text artefact by absolute or relative path."""
        p = Path(path)
        if not p.is_absolute():
            p = self._root / p
        return p.read_text(encoding="utf-8")

    def read_json(self, path: Path | str) -> Any:
        return json.loads(self.read(path))

    # ── listing ───────────────────────────────────────────────────────────────

    def list_category(self, category: str) -> List[Path]:
        cat_dir = self._root / category
        if not cat_dir.exists():
            return []
        return sorted(
            (p for p in cat_dir.iterdir() if not p.name.endswith(".meta")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def latest(self, category: str, n: int = 1) -> List[Path]:
        return self.list_category(category)[:n]

    # ── internal ──────────────────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        for sub in _SUBDIRS:
            (self._root / sub).mkdir(parents=True, exist_ok=True)

    def _resolve(self, category: str, filename: str) -> Path:
        if category not in _SUBDIRS:
            category = "generic"
        return self._root / category / filename

    def _write_meta(
        self, dest: Path, metadata: Optional[Dict[str, Any]]
    ) -> None:
        meta = {
            "path": str(dest),
            "written_at": time.time(),
            **(metadata or {}),
        }
        meta_path = dest.with_suffix(dest.suffix + ".meta")
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
