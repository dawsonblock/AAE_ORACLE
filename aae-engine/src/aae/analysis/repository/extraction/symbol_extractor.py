"""repository_intelligence/extraction/symbol_extractor — extract symbols."""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class Symbol:
    """A code symbol (function, class, variable)."""

    name: str
    kind: str           # "function" | "class" | "method" | "variable"
    file: str
    lineno: int
    end_lineno: int = 0
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)  # for classes


class SymbolExtractor:
    """Extract all symbols from Python source files."""

    def extract_file(self, path: Path) -> List[Symbol]:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            return self.extract_source(source, str(path))
        except Exception as exc:
            log.debug("SymbolExtractor failed for %s: %s", path, exc)
            return []

    def extract_from_file(self, path: Path | str) -> List[Symbol]:
        """Alias for :meth:`extract_file` accepting str or Path."""
        return self.extract_file(Path(path))

    def extract_source(
        self, source: str, filename: str = "<string>"
    ) -> List[Symbol]:
        symbols: List[Symbol] = []
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError:
            return symbols
        self._visit(tree, filename, symbols, parent_class=None)
        return symbols

    def extract_directory(self, root: Path) -> Dict[str, List[Symbol]]:
        result: Dict[str, List[Symbol]] = {}
        for p in root.rglob("*.py"):
            if ".git" not in p.parts and "__pycache__" not in p.parts:
                result[str(p)] = self.extract_file(p)
        return result

    def _visit(
        self,
        node: ast.AST,
        filename: str,
        symbols: List[Symbol],
        parent_class: Optional[str],
    ) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                bases = [
                    ast.unparse(b) if hasattr(ast, "unparse") else ""
                    for b in child.bases
                ]
                decs = [
                    ast.unparse(d) if hasattr(ast, "unparse") else ""
                    for d in child.decorator_list
                ]
                symbols.append(
                    Symbol(
                        name=child.name,
                        kind="class",
                        file=filename,
                        lineno=child.lineno,
                        end_lineno=getattr(child, "end_lineno", 0),
                        docstring=ast.get_docstring(child),
                        decorators=decs,
                        bases=bases,
                    )
                )
                self._visit(child, filename, symbols, parent_class=child.name)
            elif isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                kind = "method" if parent_class else "function"
                decs = [
                    ast.unparse(d) if hasattr(ast, "unparse") else ""
                    for d in child.decorator_list
                ]
                symbols.append(
                    Symbol(
                        name=child.name,
                        kind=kind,
                        file=filename,
                        lineno=child.lineno,
                        end_lineno=getattr(child, "end_lineno", 0),
                        docstring=ast.get_docstring(child),
                        decorators=decs,
                    )
                )
                self._visit(child, filename, symbols, parent_class=parent_class)
