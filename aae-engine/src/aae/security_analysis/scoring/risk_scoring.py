"""security_analysis/scoring/risk_scoring — CVSS-based composite risk scorer."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class RiskScore:
    """Composite risk score for a codebase or single finding."""

    raw_score: float            # 0..10 scale
    normalised: float           # 0..1
    risk_level: str             # "critical" | "high" | "medium" | "low"
    breakdown: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""


class RiskScorer:
    """Compute risk scores from sets of vulnerability data.

    Scoring formula (CVSS-inspired):
    ::

        score = Σ(cvss_i * severity_weight_i) / (1 + decay * Σ(1..n))

    where ``decay`` prevents the score from growing without bound.
    """

    _SEVERITY_WEIGHTS = {
        "critical": 1.0,
        "high": 0.75,
        "medium": 0.5,
        "low": 0.2,
        "info": 0.05,
    }

    def score_vulns(self, vulns: List[Dict]) -> RiskScore:
        """Score a list of vulnerability dicts (vuln_id, severity, cvss?)."""
        if not vulns:
            return RiskScore(
                raw_score=0.0,
                normalised=0.0,
                risk_level="low",
                explanation="No vulnerabilities found",
            )

        weighted_sum = 0.0
        breakdown: Dict[str, float] = {}
        for v in vulns:
            sev = v.get("severity", "medium")
            weight = self._SEVERITY_WEIGHTS.get(sev, 0.5)
            cvss = float(v.get("cvss") or self._default_cvss(sev))
            contribution = cvss * weight
            weighted_sum += contribution
            breakdown[sev] = breakdown.get(sev, 0.0) + contribution

        n = len(vulns)
        # Logarithmic dampening so many low-severity vulns don't dominate
        decay = 1 + 0.1 * math.log1p(n)
        raw = min(10.0, weighted_sum / decay)
        normalised = raw / 10.0

        return RiskScore(
            raw_score=round(raw, 2),
            normalised=round(normalised, 4),
            risk_level=self._level(raw),
            breakdown={k: round(v, 2) for k, v in breakdown.items()},
            explanation=(
                f"{n} vulnerabilities; weighted sum={weighted_sum:.2f}; "
                f"decay={decay:.2f}"
            ),
        )

    def score_findings(self, findings: List[Dict]) -> RiskScore:
        """Score static-analysis findings (rule_id, severity, …)."""
        return self.score_vulns(findings)  # same scoring logic

    def score(self, findings: List[Dict]) -> float:
        """Convenience wrapper: score findings and return raw float (0-10)."""
        return self.score_findings(findings).raw_score

    def aggregate(self, *scores: RiskScore) -> RiskScore:
        """Combine multiple :class:`RiskScore` objects into one."""
        if not scores:
            return RiskScore(raw_score=0.0, normalised=0.0, risk_level="low")
        avg = sum(s.raw_score for s in scores) / len(scores)
        peak = max(s.raw_score for s in scores)
        # Weighted average: 70% peak, 30% mean
        combined = 0.7 * peak + 0.3 * avg
        return RiskScore(
            raw_score=round(combined, 2),
            normalised=round(combined / 10.0, 4),
            risk_level=self._level(combined),
            explanation=f"Aggregate of {len(scores)} scores",
        )

    @staticmethod
    def _default_cvss(severity: str) -> float:
        return {"critical": 9.5, "high": 7.5, "medium": 5.0, "low": 2.5}.get(
            severity, 5.0
        )

    @staticmethod
    def _level(score: float) -> str:
        if score >= 9.0:
            return "critical"
        if score >= 7.0:
            return "high"
        if score >= 4.0:
            return "medium"
        return "low"
