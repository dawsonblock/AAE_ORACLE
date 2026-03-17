"""repository_intelligence/parsing/ast_parser — Python AST parse helpers."""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class ASTModule:
    """Parsed AST with metadata."""

    path: str
    tree: Optional[ast.Module] = None
    error: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    class_names: List[str] = field(default_factory=list)
    function_names: List[str] = field(default_factory=list)


class ASTParser:
    """Parse Python files to AST and extract top-level declarations."""

    def parse_file(self, path: Path) -> ASTModule:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            return self.parse_source(source, str(path))
        except Exception as exc:
            return ASTModule(path=str(path), error=str(exc))

    def parse_source(self, source: str, path: str = "<string>") -> ASTModule:
        try:
            tree = ast.parse(source, filename=path)
            mod = ASTModule(path=path, tree=tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        mod.imports.append(node.module)
                elif isinstance(node, ast.ClassDef):
                    mod.class_names.append(node.name)
                elif isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    mod.function_names.append(node.name)
            return mod
        except SyntaxError as exc:
            return ASTModule(path=path, error=f"SyntaxError: {exc}")

    def parse_directory(self, root: Path) -> List[ASTModule]:
        modules = []
        for p in root.rglob("*.py"):
            if ".git" not in p.parts and "__pycache__" not in p.parts:
                modules.append(self.parse_file(p))
        return modules
