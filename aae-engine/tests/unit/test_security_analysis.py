"""tests/unit/test_security_analysis.py — unit tests for security analysis engine."""
from __future__ import annotations

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# StaticAnalyzer
# ---------------------------------------------------------------------------

class TestStaticAnalyzer:
    def test_import(self):
        from aae.security_analysis.static_analysis.analyzer import StaticAnalyzer
        assert StaticAnalyzer is not None

    def test_scan_clean_code(self, tmp_path):
        from aae.security_analysis.static_analysis.analyzer import StaticAnalyzer
        f = tmp_path / "clean.py"
        f.write_text("x = 1 + 1\n")
        analyzer = StaticAnalyzer()
        findings = analyzer.scan_file(str(f))
        # Clean code should produce 0 findings
        assert isinstance(findings, list)

    def test_scan_exec_usage(self, tmp_path):
        from aae.security_analysis.static_analysis.analyzer import StaticAnalyzer
        f = tmp_path / "bad.py"
        f.write_text("exec('os.system(\"rm -rf /\")')\n")
        analyzer = StaticAnalyzer()
        findings = analyzer.scan_file(str(f))
        assert len(findings) >= 1
        severities = {fn.get("severity") for fn in findings}
        assert severities & {"high", "critical", "medium", "low"}

    def test_scan_hardcoded_secret(self, tmp_path):
        from aae.security_analysis.static_analysis.analyzer import StaticAnalyzer
        f = tmp_path / "secret.py"
        f.write_text('password = "supersecretpassword123"\n')
        analyzer = StaticAnalyzer()
        findings = analyzer.scan_file(str(f))
        assert isinstance(findings, list)


# ---------------------------------------------------------------------------
# RiskScorer
# ---------------------------------------------------------------------------

class TestRiskScorer:
    def test_import(self):
        from aae.security_analysis.scoring.risk_scoring import RiskScorer
        assert RiskScorer is not None

    def test_score_empty(self):
        from aae.security_analysis.scoring.risk_scoring import RiskScorer
        scorer = RiskScorer()
        score = scorer.score([])
        assert score == 0.0

    def test_score_high_severity(self):
        from aae.security_analysis.scoring.risk_scoring import RiskScorer
        scorer = RiskScorer()
        findings = [{"severity": "critical", "cvss": 9.8}]
        score = scorer.score(findings)
        assert score > 5.0

    def test_score_multiple_findings(self):
        from aae.security_analysis.scoring.risk_scoring import RiskScorer
        scorer = RiskScorer()
        findings = [
            {"severity": "high", "cvss": 7.5},
            {"severity": "medium", "cvss": 5.0},
            {"severity": "low", "cvss": 2.0},
        ]
        score = scorer.score(findings)
        assert score > 0.0


# ---------------------------------------------------------------------------
# SeverityClassifier
# ---------------------------------------------------------------------------

class TestSeverityClassifier:
    def test_import(self):
        from aae.security_analysis.scoring.severity_classifier import SeverityClassifier
        assert SeverityClassifier is not None

    def test_classify_critical(self):
        from aae.security_analysis.scoring.severity_classifier import SeverityClassifier
        clf = SeverityClassifier()
        sev = clf.classify({"cvss": 9.5})
        assert sev == "critical"

    def test_classify_high(self):
        from aae.security_analysis.scoring.severity_classifier import SeverityClassifier
        clf = SeverityClassifier()
        sev = clf.classify({"cvss": 7.5})
        assert sev == "high"

    def test_classify_medium(self):
        from aae.security_analysis.scoring.severity_classifier import SeverityClassifier
        clf = SeverityClassifier()
        sev = clf.classify({"cvss": 5.0})
        assert sev == "medium"

    def test_classify_low(self):
        from aae.security_analysis.scoring.severity_classifier import SeverityClassifier
        clf = SeverityClassifier()
        sev = clf.classify({"cvss": 2.0})
        assert sev == "low"


# ---------------------------------------------------------------------------
# RemediationPlanner
# ---------------------------------------------------------------------------

class TestRemediationPlanner:
    def test_import(self):
        from aae.security_analysis.remediation.remediation_planner import RemediationPlanner
        assert RemediationPlanner is not None

    def test_plan_from_empty(self):
        from aae.security_analysis.remediation.remediation_planner import RemediationPlanner
        planner = RemediationPlanner()
        plan = planner.plan_from_findings([])
        assert plan is not None
        assert plan.actions == []

    def test_plan_from_findings(self):
        from aae.security_analysis.remediation.remediation_planner import RemediationPlanner
        planner = RemediationPlanner()
        findings = [
            {"rule_id": "B101", "severity": "HIGH", "message": "assert used", "file": "x.py", "line": 5},
        ]
        plan = planner.plan_from_findings(findings)
        assert len(plan.actions) >= 1

    def test_plan_to_markdown(self):
        from aae.security_analysis.remediation.remediation_planner import RemediationPlanner
        planner = RemediationPlanner()
        findings = [{"rule_id": "B602", "severity": "CRITICAL", "message": "shell=True", "file": "run.py", "line": 10}]
        plan = planner.plan_from_findings(findings)
        md = plan.to_markdown()
        assert "## Remediation Plan" in md
