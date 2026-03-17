"""repository_intelligence/extraction/dependency_extractor — import deps."""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

log = logging.getLogger(__name__)


@dataclass
class FileDependencies:
    """Import dependencies of a single file."""

    file: str
    imports: List[str] = field(default_factory=list)         # top-level module names
    from_imports: List[str] = field(default_factory=list)    # "module.symbol"
    third_party: Set[str] = field(default_factory=set)
    stdlib: Set[str] = field(default_factory=set)
    local: Set[str] = field(default_factory=set)


class DependencyExtractor:
    """Extract import dependencies from Python files.

    Classifies imports as stdlib, third-party, or local using a simple
    heuristic: stdlib = in ``sys.stdlib_module_names`` (3.10+) or known list.
    """

    _STDLIB_FALLBACK = frozenset(
        [
            "os", "sys", "re", "ast", "abc", "io", "json", "math", "time",
            "typing", "pathlib", "logging", "collections", "dataclasses",
            "functools", "itertools", "hashlib", "subprocess", "asyncio",
            "contextlib", "inspect", "importlib", "threading", "queue",
            "socket", "http", "email", "xml", "csv", "struct", "base64",
            "copy", "enum", "gc", "hmac", "random", "string", "textwrap",
            "traceback", "unittest", "uuid", "warnings", "weakref",
        ]
    )

    def __init__(self) -> None:
        try:
            import sys
            self._stdlib: frozenset = frozenset(
                getattr(sys, "stdlib_module_names", self._STDLIB_FALLBACK)
            )
        except Exception:
            self._stdlib = self._STDLIB_FALLBACK

    def extract_file(self, path: Path) -> FileDependencies:
        fd = FileDependencies(file=str(path))
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        fd.imports.append(top)
                        self._classify(top, fd)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    top = mod.split(".")[0] if mod else ""
                    if top:
                        fd.from_imports.append(top)
                        self._classify(top, fd)
        except Exception as exc:
            log.debug("DependencyExtractor failed for %s: %s", path, exc)
        return fd

    def extract_from_file(self, path: Path | str) -> FileDependencies:
        """Alias for :meth:`extract_file` accepting str or Path."""
        return self.extract_file(Path(path))

    def extract_directory(self, root: Path) -> Dict[str, FileDependencies]:
        result: Dict[str, FileDependencies] = {}
        for p in root.rglob("*.py"):
            if ".git" not in p.parts and "__pycache__" not in p.parts:
                result[str(p)] = self.extract_file(p)
        return result

    def _classify(self, top: str, fd: FileDependencies) -> None:
        if top in self._stdlib:
            fd.stdlib.add(top)
        elif top.startswith(".") or top == "":
            fd.local.add(top)
        else:
            fd.third_party.add(top)
