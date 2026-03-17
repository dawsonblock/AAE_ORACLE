"""security_analysis/remediation/remediation_planner — ordered fix plans.

Generates a prioritised, actionable remediation plan from a mixed set of
static-analysis findings, dependency vulnerabilities, and risk scores.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class RemediationAction:
    """A single remediation step."""

    action_id: str
    priority: int               # 1 = highest
    category: str               # "dependency_upgrade" | "code_fix" | "config" | "review"
    title: str
    description: str
    affected_component: str
    effort: str = "medium"      # "low" | "medium" | "high"
    automated: bool = False     # can the AAE apply this automatically?
    patch_hint: Optional[str] = None   # e.g. "upgrade requests to >=2.31.0"


@dataclass
class RemediationPlan:
    """Complete remediation plan for a codebase security assessment."""

    actions: List[RemediationAction] = field(default_factory=list)
    total_actions: int = 0
    automated_count: int = 0
    estimated_effort: str = "medium"

    def critical_actions(self) -> List[RemediationAction]:
        return [a for a in self.actions if a.priority <= 3]

    def automated_actions(self) -> List[RemediationAction]:
        return [a for a in self.actions if a.automated]

    def to_markdown(self) -> str:
        lines = ["## Remediation Plan", ""]
        for action in self.actions:
            auto = "✅ Auto" if action.automated else "🔧 Manual"
            lines.append(
                f"## P{action.priority} [{action.category}] {action.title} ({auto})"
            )
            lines.append(f"**Component**: {action.affected_component}")
            lines.append(f"**Effort**: {action.effort}")
            lines.append(f"\n{action.description}\n")
            if action.patch_hint:
                lines.append(f"**Hint**: `{action.patch_hint}`\n")
        return "\n".join(lines)


class RemediationPlanner:
    """Build a :class:`RemediationPlan` from security analysis outputs.

    Parameters
    ----------
    auto_upgrade_threshold:
        CVSS score threshold above which dependency upgrades are marked as
        high-priority automated actions.
    """

    def __init__(self, auto_upgrade_threshold: float = 7.0) -> None:
        self._auto_threshold = auto_upgrade_threshold
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"REM-{self._counter:04d}"

    def plan_from_vulns(
        self, scan_results: List[Dict]
    ) -> RemediationPlan:
        """Build plan from VulnerabilityDBClient scan results.

        Each item: package_name, version, vulnerabilities (list of vuln dicts).
        """
        actions: List[RemediationAction] = []
        for result in scan_results:
            pkg = result.get("package_name", "unknown")
            ver = result.get("version", "?")
            for vuln in result.get("vulnerabilities", []):
                cvss = float(vuln.get("cvss_score") or 5.0)
                severity = vuln.get("severity", "medium")
                fixed = vuln.get("fixed_version")
                priority = self._sev_to_priority(severity)
                actions.append(
                    RemediationAction(
                        action_id=self._next_id(),
                        priority=priority,
                        category="dependency_upgrade",
                        title=f"Upgrade {pkg} (CVE: {vuln.get('vuln_id', '?')})",
                        description=(
                            f"{pkg}@{ver} has vulnerability {vuln.get('vuln_id')}: "
                            f"{vuln.get('summary', '')}"
                        ),
                        affected_component=pkg,
                        effort="low",
                        automated=cvss >= self._auto_threshold and fixed is not None,
                        patch_hint=(
                            f"upgrade {pkg} to >={fixed}" if fixed else None
                        ),
                    )
                )
        return self._finalise(actions)

    def plan_from_findings(
        self, findings: List[Dict]
    ) -> RemediationPlan:
        """Build plan from StaticAnalyzer / ASTSecurityScanner findings.

        Each item: rule_id, severity, file, line, message, code_snippet?.
        """
        actions: List[RemediationAction] = []
        for f in findings:
            severity = f.get("severity", "medium")
            priority = self._sev_to_priority(severity)
            automated = f.get("rule_id", "").startswith("SA1")  # secrets only
            actions.append(
                RemediationAction(
                    action_id=self._next_id(),
                    priority=priority,
                    category="code_fix",
                    title=f"Fix {f.get('rule_id', '?')}: {f.get('message', '')}",
                    description=(
                        f"File: {f.get('file', '?')} line {f.get('line', '?')}\n"
                        f"Snippet: {f.get('code_snippet', '')}"
                    ),
                    affected_component=f.get("file", "unknown"),
                    effort=self._sev_to_effort(severity),
                    automated=automated,
                )
            )
        return self._finalise(actions)

    def merge(self, *plans: RemediationPlan) -> RemediationPlan:
        """Merge multiple plans into one, re-sorted by priority."""
        all_actions: List[RemediationAction] = []
        for p in plans:
            all_actions.extend(p.actions)
        return self._finalise(all_actions)

    # ── internals ─────────────────────────────────────────────────────────────

    def _finalise(self, actions: List[RemediationAction]) -> RemediationPlan:
        actions.sort(key=lambda a: a.priority)
        auto_count = sum(1 for a in actions if a.automated)
        total_effort = self._aggregate_effort(actions)
        return RemediationPlan(
            actions=actions,
            total_actions=len(actions),
            automated_count=auto_count,
            estimated_effort=total_effort,
        )

    @staticmethod
    def _sev_to_priority(severity: str) -> int:
        return {"critical": 1, "high": 2, "medium": 3, "low": 4, "info": 5}.get(
            severity, 3
        )

    @staticmethod
    def _sev_to_effort(severity: str) -> str:
        return {"critical": "high", "high": "medium", "medium": "low"}.get(
            severity, "low"
        )

    @staticmethod
    def _aggregate_effort(actions: List[RemediationAction]) -> str:
        if any(a.effort == "high" for a in actions):
            return "high"
        if any(a.effort == "medium" for a in actions):
            return "medium"
        return "low"
