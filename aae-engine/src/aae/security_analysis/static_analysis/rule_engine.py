"""security_analysis/static_analysis/rule_engine — YAML-driven rule loader.

Rules are stored as YAML (or dict) and compiled to regex patterns that the
:class:`StaticAnalyzer` can consume as *extra_rules*.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ── data model ──────────────────────────────────────────────────────────────


@dataclass
class Rule:
    rule_id: str
    severity: str
    pattern: str
    message: str
    cwe: Optional[str] = None
    languages: List[str] = field(default_factory=lambda: ["python"])
    enabled: bool = True
    _compiled: Optional[re.Pattern] = field(default=None, init=False, repr=False)

    def compile(self) -> "Rule":
        self._compiled = re.compile(self.pattern, re.MULTILINE)
        return self

    def match(self, source: str) -> List[re.Match]:
        if self._compiled is None:
            self.compile()
        assert self._compiled is not None
        return list(self._compiled.finditer(source))


# ── engine ───────────────────────────────────────────────────────────────────


class RuleEngine:
    """Load security rules from YAML files or plain dicts.

    Usage::

        engine = RuleEngine.from_yaml(Path("configs/security_rules.yaml"))
        rules = engine.as_extra_rules()  # pass to StaticAnalyzer
    """

    def __init__(self, rules: Optional[List[Rule]] = None) -> None:
        self._rules: List[Rule] = rules or []

    # ── constructors ─────────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleEngine":
        rules: List[Rule] = []
        for item in data.get("rules", []):
            try:
                rules.append(
                    Rule(
                        rule_id=item["id"],
                        severity=item.get("severity", "medium"),
                        pattern=item["pattern"],
                        message=item.get("message", item["id"]),
                        cwe=item.get("cwe"),
                        languages=item.get("languages", ["python"]),
                        enabled=item.get("enabled", True),
                    ).compile()
                )
            except (KeyError, re.error) as exc:
                log.warning("Skipping bad rule %s: %s", item.get("id"), exc)
        return cls(rules)

    @classmethod
    def from_yaml(cls, path: Path) -> "RuleEngine":
        try:
            import yaml  # type: ignore[import]
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return cls.from_dict(data or {})
        except ImportError:
            log.warning("PyYAML not installed — rule file %s skipped", path)
            return cls()
        except Exception as exc:
            log.error("Failed to load rule file %s: %s", path, exc)
            return cls()

    @classmethod
    def from_directory(cls, directory: Path) -> "RuleEngine":
        """Merge all ``*.yaml`` / ``*.yml`` rule files in *directory*."""
        combined: List[Rule] = []
        for yaml_path in sorted(directory.glob("*.y*ml")):
            combined.extend(cls.from_yaml(yaml_path)._rules)
        return cls(combined)

    # ── public API ───────────────────────────────────────────────────────────

    @property
    def rules(self) -> List[Rule]:
        return [r for r in self._rules if r.enabled]

    def add(self, rule: Rule) -> None:
        rule.compile()
        self._rules.append(rule)

    def disable(self, rule_id: str) -> None:
        for r in self._rules:
            if r.rule_id == rule_id:
                r.enabled = False

    def as_extra_rules(self) -> List[tuple]:
        """Return rules in the format expected by :class:`StaticAnalyzer`."""
        return [
            (r.rule_id, r.severity, r.pattern, r.message, r.cwe or "")
            for r in self.rules
        ]

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self._rules:
            counts[r.severity] = counts.get(r.severity, 0) + 1
        return counts
