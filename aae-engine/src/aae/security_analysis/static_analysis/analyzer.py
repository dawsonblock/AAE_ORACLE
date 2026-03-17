"""security_analysis/static_analysis/analyzer — Python static security scanner.

Combines AST-level analysis (``ast_security_scanner``) with rule-based
pattern matching (``rule_engine``) to produce a list of findings.
"""
from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class Finding:
    """A single security finding."""

    rule_id: str
    severity: str          # "critical" | "high" | "medium" | "low" | "info"
    file: str
    line: int
    message: str
    code_snippet: str = ""
    cwe: Optional[str] = None


@dataclass
class AnalysisResult:
    """Aggregated output of a static analysis run."""

    findings: List[Finding] = field(default_factory=list)
    files_scanned: int = 0
    errors: List[str] = field(default_factory=list)

    def critical(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "critical"]

    def high(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == "high"]

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts


class StaticAnalyzer:
    """Scan Python source files for security anti-patterns.

    Parameters
    ----------
    rules:
        List of ``(rule_id, severity, regex_pattern, message, cwe)`` tuples.
        Additional rules are appended to the built-in set.
    use_bandit:
        If ``True`` and ``bandit`` is installed, also run bandit and merge.
    """

    BUILTIN_RULES: List[tuple[str, str, str, str, str]] = [
        # (rule_id, severity, pattern, message, cwe)
        ("SA001", "high", r"eval\s*\(", "Use of eval()", "CWE-78"),
        ("SA002", "high", r"exec\s*\(", "Use of exec()", "CWE-78"),
        ("SA003", "medium", r"pickle\.loads?\s*\(", "Unsafe pickle usage", "CWE-502"),
        ("SA004", "medium", r"subprocess\.call\s*\(.*shell\s*=\s*True", "Shell injection risk", "CWE-78"),
        ("SA005", "low", r"assert\s+", "Assertions disabled with -O flag", "CWE-617"),
        ("SA006", "high", r"__import__\s*\(", "Dynamic import", "CWE-913"),
        ("SA007", "medium", r"random\.", "Weak PRNG for security", "CWE-338"),
        ("SA008", "critical", r"hashlib\.md5\s*\(", "Weak MD5 hash", "CWE-327"),
        ("SA009", "critical", r"hashlib\.sha1\s*\(", "Weak SHA-1 hash", "CWE-327"),
        ("SA010", "high", r"ssl\.CERT_NONE", "SSL cert verification disabled", "CWE-295"),
    ]

    def __init__(
        self,
        extra_rules: Optional[List[tuple]] = None,
        use_bandit: bool = True,
    ) -> None:
        self._rules = list(self.BUILTIN_RULES)
        if extra_rules:
            self._rules.extend(extra_rules)
        self._compiled = [
            (rid, sev, re.compile(pat, re.MULTILINE), msg, cwe)
            for rid, sev, pat, msg, cwe in self._rules
        ]
        self._use_bandit = use_bandit

    def _scan_file_internal(self, path: Path | str) -> AnalysisResult:
        """Scan a single Python file and return an AnalysisResult."""
        path = Path(path)
        result = AnalysisResult(files_scanned=1)
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            lines = source.splitlines()
            result.findings.extend(self._pattern_scan(path, source, lines))
            result.findings.extend(self._ast_scan(path, source, lines))
        except Exception as exc:
            result.errors.append(f"{path}: {exc}")
        return result

    def scan_file(self, path: Path | str) -> List[Dict]:
        """Scan a single Python file; return findings as a list of dicts.

        Severity values are returned in the original lowercase form used
        internally ("critical", "high", "medium", "low", "info").
        """
        result = self._scan_file_internal(path)
        return [
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "file": f.file,
                "line": f.line,
                "message": f.message,
                "code_snippet": f.code_snippet,
                "cwe": f.cwe,
            }
            for f in result.findings
        ]

    def scan_directory(self, root: Path, glob: str = "**/*.py") -> AnalysisResult:
        """Scan all Python files under *root*."""
        combined = AnalysisResult()
        for path in root.glob(glob):
            r = self._scan_file_internal(path)
            combined.findings.extend(r.findings)
            combined.files_scanned += r.files_scanned
            combined.errors.extend(r.errors)
        if self._use_bandit:
            combined.findings.extend(self._run_bandit(root))
        return combined

    def _run_bandit(self, root: Path) -> List[Finding]:
        """Run bandit on *root* and return findings (best-effort)."""
        try:
            import subprocess
            import json as _json
            result = subprocess.run(
                ["bandit", "-r", str(root), "-f", "json", "-q"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            data = _json.loads(result.stdout or "{}")
            findings: List[Finding] = []
            for issue in data.get("results", []):
                findings.append(Finding(
                    rule_id=issue.get("test_id", "B000"),
                    severity=issue.get("issue_severity", "medium").lower(),
                    file=issue.get("filename", ""),
                    line=issue.get("line_number", 0),
                    message=issue.get("issue_text", ""),
                    code_snippet=issue.get("code", "").strip(),
                    cwe=issue.get("issue_cwe", {}).get("id"),
                ))
            return findings
        except Exception as exc:
            log.debug("bandit run failed: %s", exc)
            return []

    def _pattern_scan(
        self, path: Path, source: str, lines: List[str]
    ) -> List[Finding]:
        findings: List[Finding] = []
        for rid, sev, pat, msg, cwe in self._compiled:
            for m in pat.finditer(source):
                lineno = source[: m.start()].count("\n") + 1
                snippet = lines[lineno - 1].strip() if lineno <= len(lines) else ""
                findings.append(
                    Finding(
                        rule_id=rid,
                        severity=sev,
                        file=str(path),
                        line=lineno,
                        message=msg,
                        code_snippet=snippet,
                        cwe=cwe,
                    )
                )
        return findings

    def _ast_scan(
        self, path: Path, source: str, lines: List[str]
    ) -> List[Finding]:
        findings: List[Finding] = []
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return findings
        for node in ast.walk(tree):
            # Detect hard-coded passwords
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name_lower = target.id.lower()
                        if any(
                            kw in name_lower
                            for kw in ("password", "passwd", "secret", "token")
                        ):
                            if isinstance(node.value, ast.Constant):
                                lineno = node.lineno
                                snippet = (
                                    lines[lineno - 1].strip()
                                    if lineno <= len(lines)
                                    else ""
                                )
                                findings.append(
                                    Finding(
                                        rule_id="SA100",
                                        severity="critical",
                                        file=str(path),
                                        line=lineno,
                                        message="Hardcoded secret detected",
                                        code_snippet=snippet,
                                        cwe="CWE-798",
                                    )
                                )
        return findings


