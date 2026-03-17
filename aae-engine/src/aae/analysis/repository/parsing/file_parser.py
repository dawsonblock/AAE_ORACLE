"""repository_intelligence/parsing/file_parser — language-aware file parser."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

_EXT_LANG: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".rb": "ruby",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".sh": "bash",
}


@dataclass
class ParsedFile:
    """Parsed representation of a source file."""

    path: str
    language: str
    content: str
    lines: int = 0
    size_bytes: int = 0
    encoding: str = "utf-8"
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.lines:
            self.lines = self.content.count("\n") + 1
        if not self.size_bytes:
            self.size_bytes = len(self.content.encode(self.encoding, "replace"))


class FileParser:
    """Read source files and produce :class:`ParsedFile` objects.

    Parameters
    ----------
    repo_root:
        Repository root for computing relative paths.
    max_size_kb:
        Skip files larger than this threshold.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        max_size_kb: int = 512,
    ) -> None:
        self._root = repo_root or Path(".")
        self._max_bytes = max_size_kb * 1024

    def parse_file(self, path: Path | str) -> ParsedFile:
        path = Path(path)
        rel = str(path.relative_to(self._root)) if (
            path.is_absolute()
            and str(path).startswith(str(self._root))
        ) else str(path)
        lang = _EXT_LANG.get(path.suffix.lower(), "text")
        try:
            if path.stat().st_size > self._max_bytes:
                return ParsedFile(
                    path=rel,
                    language=lang,
                    content="",
                    error=f"File too large (>{self._max_bytes//1024} KB)",
                )
            content = path.read_text(encoding="utf-8", errors="replace")
            return ParsedFile(path=rel, language=lang, content=content)
        except Exception as exc:
            return ParsedFile(path=rel, language=lang, content="", error=str(exc))

    def parse_directory(
        self,
        root: Path | str | None = None,
        extensions: Optional[List[str]] = None,
    ) -> List[ParsedFile]:
        scan_root = Path(root) if root is not None else self._root
        exts = frozenset(extensions or list(_EXT_LANG.keys()))
        files = []
        for p in scan_root.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts:
                if ".git" in p.parts or "node_modules" in p.parts:
                    continue
                files.append(self.parse_file(p))
        return files

    def language_breakdown(self, files: List[ParsedFile]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for f in files:
            counts[f.language] = counts.get(f.language, 0) + 1
        return counts
