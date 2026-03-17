"""security_analysis/static_analysis/ast_security_scanner — AST-level checks.

Uses Python's ``ast`` module to detect semantic issues that regex patterns
miss, such as hard-coded secrets, risky attribute chains, and unsafe calls.
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# ── shared data model (mirrors analyzer.Finding) ─────────────────────────────


@dataclass
class ASTFinding:
    rule_id: str
    severity: str
    file: str
    line: int
    col: int
    message: str
    code_snippet: str = ""
    cwe: Optional[str] = None


# ── visitor ───────────────────────────────────────────────────────────────────


class _SecurityVisitor(ast.NodeVisitor):
    """Walk an AST tree and collect security findings."""

    _SECRET_NAMES = frozenset(
        ["password", "passwd", "secret", "api_key", "apikey", "token", "auth"]
    )
    _DANGEROUS_CALLS = {
        "eval": ("SA001", "high", "Use of eval()", "CWE-78"),
        "exec": ("SA002", "high", "Use of exec()", "CWE-78"),
        "compile": ("SA200", "medium", "Dynamic code compile()", "CWE-913"),
        "input": ("SA201", "low", "User input via input()", "CWE-20"),
    }
    _UNSAFE_MODULES = {
        "pickle": ("SA300", "high", "Unsafe pickle import", "CWE-502"),
        "shelve": ("SA301", "medium", "Unsafe shelve import", "CWE-502"),
        "marshal": ("SA302", "medium", "Unsafe marshal import", "CWE-502"),
        "yaml": ("SA303", "low", "yaml.load without Loader", "CWE-502"),
    }

    def __init__(self, source_lines: List[str], filename: str) -> None:
        self._lines = source_lines
        self._filename = filename
        self.findings: List[ASTFinding] = []

    def _snippet(self, lineno: int) -> str:
        idx = lineno - 1
        return self._lines[idx].strip() if 0 <= idx < len(self._lines) else ""

    def _add(
        self,
        rule_id: str,
        severity: str,
        message: str,
        cwe: Optional[str],
        node: ast.AST,
    ) -> None:
        lineno = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0)
        self.findings.append(
            ASTFinding(
                rule_id=rule_id,
                severity=severity,
                file=self._filename,
                line=lineno,
                col=col,
                message=message,
                code_snippet=self._snippet(lineno),
                cwe=cwe,
            )
        )

    # ── visitors ──────────────────────────────────────────────────────────────

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                if target.id.lower() in self._SECRET_NAMES:
                    if isinstance(node.value, ast.Constant) and isinstance(
                        node.value.value, str
                    ):
                        self._add(
                            "SA100",
                            "critical",
                            f"Hardcoded secret in variable '{target.id}'",
                            "CWE-798",
                            node,
                        )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # bare function calls: eval(), exec(), …
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in self._DANGEROUS_CALLS:
            rid, sev, msg, cwe = self._DANGEROUS_CALLS[func_name]
            self._add(rid, sev, msg, cwe, node)

        # subprocess with shell=True
        if func_name in ("call", "run", "Popen", "check_output", "check_call"):
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant):
                    if kw.value.value is True:
                        self._add(
                            "SA004",
                            "high",
                            "subprocess called with shell=True",
                            "CWE-78",
                            node,
                        )

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in self._UNSAFE_MODULES:
                rid, sev, msg, cwe = self._UNSAFE_MODULES[top]
                self._add(rid, sev, msg, cwe, node)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        top = module.split(".")[0]
        if top in self._UNSAFE_MODULES:
            rid, sev, msg, cwe = self._UNSAFE_MODULES[top]
            self._add(rid, sev, msg, cwe, node)
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self._add(
            "SA005",
            "low",
            "assert statement (disabled by -O flag)",
            "CWE-617",
            node,
        )
        self.generic_visit(node)


# ── public class ──────────────────────────────────────────────────────────────


class ASTSecurityScanner:
    """Scan Python files using AST-based analysis."""

    def scan_file(self, path: Path) -> List[ASTFinding]:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            lines = source.splitlines()
            tree = ast.parse(source, filename=str(path))
            visitor = _SecurityVisitor(lines, str(path))
            visitor.visit(tree)
            return visitor.findings
        except SyntaxError as exc:
            log.debug("AST parse failed for %s: %s", path, exc)
            return []
        except Exception as exc:
            log.warning("AST scan error for %s: %s", path, exc)
            return []

    def scan_source(self, source: str, filename: str = "<string>") -> List[ASTFinding]:
        try:
            lines = source.splitlines()
            tree = ast.parse(source, filename=filename)
            visitor = _SecurityVisitor(lines, filename)
            visitor.visit(tree)
            return visitor.findings
        except SyntaxError:
            return []
