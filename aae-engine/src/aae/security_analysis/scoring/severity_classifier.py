"""security_analysis/scoring/severity_classifier — classify severity levels.

Classifies vulnerability or finding severity using CVSS scores and keyword
heuristics when a CVSS score is not available.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional


class SeverityClassifier:
    """Classify security findings into severity tiers.

    Parameters
    ----------
    custom_thresholds:
        Override CVSS thresholds. Keys: "critical", "high", "medium", "low".
    """

    _DEFAULT_THRESHOLDS: Dict[str, float] = {
        "critical": 9.0,
        "high": 7.0,
        "medium": 4.0,
        "low": 0.1,
    }

    _CRITICAL_KEYWORDS = frozenset(
        [
            "remote code execution",
            "rce",
            "arbitrary code",
            "privilege escalation",
            "root",
            "full compromise",
        ]
    )
    _HIGH_KEYWORDS = frozenset(
        [
            "sql injection",
            "xxe",
            "ssrf",
            "authentication bypass",
            "hardcoded secret",
            "deserialization",
        ]
    )
    _MEDIUM_KEYWORDS = frozenset(
        ["xss", "csrf", "path traversal", "open redirect", "information disclosure"]
    )

    def __init__(
        self, custom_thresholds: Optional[Dict[str, float]] = None
    ) -> None:
        self._thresholds = {**self._DEFAULT_THRESHOLDS, **(custom_thresholds or {})}

    def classify_cvss(self, score: float) -> str:
        """Return severity string for a CVSS numeric *score*."""
        if score >= self._thresholds["critical"]:
            return "critical"
        if score >= self._thresholds["high"]:
            return "high"
        if score >= self._thresholds["medium"]:
            return "medium"
        if score >= self._thresholds["low"]:
            return "low"
        return "info"

    def classify_text(self, text: str) -> str:
        """Classify severity from free-text description using keywords."""
        lower = text.lower()
        for kw in self._CRITICAL_KEYWORDS:
            if kw in lower:
                return "critical"
        for kw in self._HIGH_KEYWORDS:
            if kw in lower:
                return "high"
        for kw in self._MEDIUM_KEYWORDS:
            if kw in lower:
                return "medium"
        return "low"

    def classify(
        self, cvss_or_finding=None, text: Optional[str] = None,
        cvss: Optional[float] = None,
    ) -> str:
        """Classify with CVSS taking precedence over text heuristics.

        Accepts either a CVSS float, a dict with a ``cvss`` key, or free text.
        """
        # Support dict input: classify({"cvss": 9.5})
        if isinstance(cvss_or_finding, dict):
            cvss = cvss_or_finding.get("cvss", cvss)
            text = text or cvss_or_finding.get("summary") or cvss_or_finding.get("message")
        elif isinstance(cvss_or_finding, (int, float)):
            cvss = float(cvss_or_finding)
        if cvss is not None:
            return self.classify_cvss(float(cvss))
        if text:
            return self.classify_text(text)
        return "medium"

    def batch_classify(self, items: List[Dict]) -> List[Dict]:
        """Classify a list of dicts (cvss?, summary?, severity?) in-place.

        Each item gets a ``"severity"`` key set to the computed tier.
        """
        for item in items:
            item["severity"] = self.classify(
                cvss=item.get("cvss"),
                text=item.get("summary") or item.get("description"),
            )
        return items

    def severity_order(self, severity: str) -> int:
        """Return numeric order (higher = more severe)."""
        return {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}.get(
            severity, 0
        )

    def sort_by_severity(self, items: List[Dict]) -> List[Dict]:
        """Sort a list of dicts descending by severity."""
        return sorted(
            items,
            key=lambda x: self.severity_order(x.get("severity", "low")),
            reverse=True,
        )
