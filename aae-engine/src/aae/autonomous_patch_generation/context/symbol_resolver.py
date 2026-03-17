"""autonomous_patch_generation/context/symbol_resolver — resolve code symbols."""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    """Resolved symbol metadata."""

    name: str
    kind: str           # "function" | "class" | "method" | "variable"
    file: str
    lineno: int
    docstring: Optional[str] = None
    signature: Optional[str] = None
    references: List[str] = field(default_factory=list)


class SymbolResolver:
    """Resolve Python symbols within a repository using ``ast``.

    Parameters
    ----------
    repo_root:
        Root of the repository.
    """

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self._root = repo_root or Path(".")
        self._index: Dict[str, SymbolInfo] = {}
        self._indexed = False

    def index(self) -> None:
        """Build symbol index for all Python files under *repo_root*."""
        for path in self._root.rglob("*.py"):
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self._index_func(node, path)
                    elif isinstance(node, ast.ClassDef):
                        self._index_class(node, path)
            except Exception:
                pass
        self._indexed = True

    def resolve(self, name: str) -> Optional[SymbolInfo]:
        """Look up *name* in the index (may trigger indexing)."""
        if not self._indexed:
            self.index()
        return self._index.get(name)

    def resolve_many(self, names: List[str]) -> Dict[str, SymbolInfo]:
        if not self._indexed:
            self.index()
        return {n: self._index[n] for n in names if n in self._index}

    # ── internals ─────────────────────────────────────────────────────────────

    def _index_func(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, path: Path
    ) -> None:
        docstring = ast.get_docstring(node) or None
        args = [a.arg for a in node.args.args]
        sig = f"{node.name}({', '.join(args)})"
        kind = "method" if self._is_method(node) else "function"
        info = SymbolInfo(
            name=node.name,
            kind=kind,
            file=str(path.relative_to(self._root)),
            lineno=node.lineno,
            docstring=docstring,
            signature=sig,
        )
        self._index[node.name] = info

    def _index_class(self, node: ast.ClassDef, path: Path) -> None:
        docstring = ast.get_docstring(node) or None
        info = SymbolInfo(
            name=node.name,
            kind="class",
            file=str(path.relative_to(self._root)),
            lineno=node.lineno,
            docstring=docstring,
        )
        self._index[node.name] = info

    @staticmethod
    def _is_method(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        # Heuristic: first argument is "self" or "cls"
        args = node.args.args
        return bool(args and args[0].arg in ("self", "cls"))
