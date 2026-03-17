"""autonomous_patch_generation/validation/patch_validator — validate patches."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Full validation report for a patch candidate."""

    patch_id: str
    approved: bool = False
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class PatchValidator:
    """Orchestrate all validation gates for a generated patch.

    Gates (in order):
    1. Pre-flight simulation must be safe.
    2. Test run must succeed (no regressions).
    3. Patch score must exceed *min_score*.
    4. Patch must not be empty.

    Parameters
    ----------
    min_score:
        Minimum :class:`PatchScore`.total to approve a patch.
    require_ftp:
        If True, at least one fail-to-pass test is required.
    """

    def __init__(
        self, min_score: float = 0.6, require_ftp: bool = False
    ) -> None:
        self._min_score = min_score
        self._require_ftp = require_ftp

    def validate(
        self,
        patch,
        simulation=None,
        test_run=None,
        score=None,
    ) -> ValidationResult:
        # Accept both a patch object and a raw diff string
        if isinstance(patch, str):
            diff_text = patch
            patch_id = "<inline>"
        else:
            diff_text = getattr(patch, "diff", "")
            patch_id = getattr(patch, "patch_id", "<unknown>")

        result = ValidationResult(patch_id=patch_id)

        # Gate 1: empty patch
        if not diff_text.strip():
            result.reasons.append("Patch diff is empty")
            return result

        # Gate 2: simulation
        if simulation is not None:
            if not getattr(simulation, "safe_to_apply", True):
                for issue in getattr(simulation, "issues", []):
                    result.reasons.append(f"Simulation: {issue}")
                return result
            for warn in getattr(simulation, "warnings", []):
                result.warnings.append(f"Simulation: {warn}")

        # Gate 3: test regression check
        if test_run is not None:
            if not getattr(test_run, "success", True):
                result.reasons.append(
                    f"Tests failed: {getattr(test_run, 'failed', '?')} failures"
                )
                return result
            ptf = getattr(test_run, "pass_to_fail", [])
            if ptf:
                result.reasons.append(
                    f"Regressions: {len(ptf)} tests went pass→fail"
                )
                return result
            ftp = getattr(test_run, "fail_to_pass", [])
            if self._require_ftp and not ftp:
                result.reasons.append("No fail-to-pass tests (required)")
                return result

        # Gate 4: score threshold
        if score is not None:
            total = getattr(score, "total", 0.0)
            result.score = total
            if total < self._min_score:
                result.reasons.append(
                    f"Score {total:.2f} below threshold {self._min_score}"
                )
                return result

        result.approved = True
        return result
