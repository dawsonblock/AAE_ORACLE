from __future__ import annotations

import re
from typing import Any, Dict, List

from aae.integrations.models import SecurityFinding, SecurityReport


class AgentShieldBridge:
    """Python security gate shaped around AgentShield categories."""

    SECRET_PATTERNS = {
        'anthropic_key': r'sk-ant-[A-Za-z0-9_-]+',
        'openai_key': r'sk-(proj|live|test)-[A-Za-z0-9_-]+',
        'aws_key': r'AKIA[0-9A-Z]{16}',
        'github_pat': r'(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]+)',
    }
    DANGEROUS_COMMANDS = (
        'rm -rf /', 'format c:', 'shutdown /s', 'curl http', 'wget http', 'scp ', 'ssh ',
        'chmod 777', 'git push --force', 'git reset --hard', 'sudo ', 'exfiltrate'
    )
    DANGEROUS_PERMS = ('Bash(*)', 'Write(*)', 'Edit(*)', '--dangerously-skip-permissions')
    PROMPT_INJECTION = (
        'ignore previous instructions', 'you are now', 'always run', 'without asking',
        'download and execute', 'automatically install'
    )

    def scan_payload(self, payload: Dict[str, Any]) -> SecurityReport:
        text = str(payload)
        findings: List[SecurityFinding] = []
        findings.extend(self._scan_secrets(text))
        findings.extend(self._scan_commands(text))
        findings.extend(self._scan_permissions(text))
        findings.extend(self._scan_prompt_injection(text))

        critical = sum(1 for f in findings if f.severity == 'critical')
        high = sum(1 for f in findings if f.severity == 'high')
        medium = sum(1 for f in findings if f.severity == 'medium')
        score = max(0, 100 - critical * 25 - high * 12 - medium * 5)
        grade = self._grade(score)
        allowed = critical == 0 and not any('download and execute' in f.message.lower() for f in findings)
        return SecurityReport(allowed=allowed, score=score, grade=grade, findings=findings)

    def _scan_secrets(self, text: str) -> List[SecurityFinding]:
        results = []
        for name, pattern in self.SECRET_PATTERNS.items():
            match = re.search(pattern, text)
            if match:
                results.append(SecurityFinding(
                    severity='critical',
                    category='secrets',
                    message=f'Hardcoded secret detected: {name}',
                    evidence=match.group(0)[:24],
                    auto_fixable=True,
                ))
        return results

    def _scan_commands(self, text: str) -> List[SecurityFinding]:
        results = []
        lowered = text.lower()
        for item in self.DANGEROUS_COMMANDS:
            if item.lower() in lowered:
                results.append(SecurityFinding(
                    severity='critical' if item in {'rm -rf /', 'format c:', 'sudo ', 'exfiltrate'} else 'high',
                    category='hooks' if 'curl' in item or 'wget' in item else 'permissions',
                    message=f'Dangerous command pattern: {item}',
                    evidence=item,
                ))
        return results

    def _scan_permissions(self, text: str) -> List[SecurityFinding]:
        results = []
        for item in self.DANGEROUS_PERMS:
            if item in text:
                results.append(SecurityFinding(
                    severity='high',
                    category='permissions',
                    message=f'Overly broad permission: {item}',
                    evidence=item,
                ))
        return results

    def _scan_prompt_injection(self, text: str) -> List[SecurityFinding]:
        lowered = text.lower()
        results = []
        for item in self.PROMPT_INJECTION:
            if item in lowered:
                results.append(SecurityFinding(
                    severity='medium',
                    category='agents',
                    message=f'Prompt injection / unsafe instruction surface: {item}',
                    evidence=item,
                ))
        return results

    def _grade(self, score: int) -> str:
        if score >= 90:
            return 'A'
        if score >= 80:
            return 'B'
        if score >= 70:
            return 'C'
        if score >= 60:
            return 'D'
        return 'F'
