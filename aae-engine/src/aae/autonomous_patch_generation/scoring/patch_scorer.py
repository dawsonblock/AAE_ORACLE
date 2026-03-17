"""autonomous_patch_generation/scoring/patch_scorer — score patches."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class PatchScore:
    """Multi-dimensional score for a generated patch."""

    patch_id: str
    total: float = 0.0          # 0..1 composite
    test_score: float = 0.0     # test pass-rate contribution
    safety_score: float = 0.0   # 1 - risk_score from simulator
    coverage_delta: float = 0.0 # change in code coverage
    size_penalty: float = 0.0   # penalise very large patches
    explanation: str = ""

    def is_acceptable(self, threshold: float = 0.6) -> bool:
        return self.total >= threshold


class PatchScorer:
    """Compute a composite :class:`PatchScore` from test and simulation data.

    Parameters
    ----------
    w_test:
        Weight for test pass-rate component (default 0.5).
    w_safety:
        Weight for safety component (default 0.35).
    w_coverage:
        Weight for coverage delta (default 0.15).
    """

    def __init__(
        self,
        w_test: float = 0.50,
        w_safety: float = 0.35,
        w_coverage: float = 0.15,
    ) -> None:
        self._w_test = w_test
        self._w_safety = w_safety
        self._w_cov = w_coverage

    def score(
        self,
        patch_id: str,
        test_run=None,
        simulation=None,
        coverage_delta: float = 0.0,
        test_outcome=None,   # alias for test_run
    ) -> float:
        """Return composite score as a float in [0, 1].

        Use :meth:`score_detailed` when you need the full
        :class:`PatchScore` breakdown.
        """
        if test_run is None and test_outcome is not None:
            test_run = test_outcome
        return self.score_detailed(
            patch_id, test_run=test_run,
            simulation=simulation, coverage_delta=coverage_delta,
        ).total

    def score_detailed(
        self,
        patch_id: str,
        test_run=None,
        simulation=None,
        coverage_delta: float = 0.0,
    ) -> PatchScore:
        ps = PatchScore(patch_id=patch_id)

        # Test component
        if test_run is not None:
            ps.test_score = getattr(test_run, "pass_rate", lambda: 0.0)()
            ftp = len(getattr(test_run, "fail_to_pass", []))
            ptf = len(getattr(test_run, "pass_to_fail", []))
            # Bonus for fail-to-pass, penalty for pass-to-fail
            ps.test_score = min(1.0, ps.test_score + ftp * 0.05 - ptf * 0.1)

        # Safety component
        if simulation is not None:
            risk = getattr(simulation, "risk_score", 0.5)
            ps.safety_score = 1.0 - risk

        # Coverage component
        ps.coverage_delta = max(-1.0, min(1.0, coverage_delta))

        # Size penalty (prefer small patches)
        ps.size_penalty = 0.0

        ps.total = round(
            self._w_test * ps.test_score
            + self._w_safety * ps.safety_score
            + self._w_cov * (0.5 + ps.coverage_delta * 0.5),
            4,
        )
        ps.explanation = (
            f"test={ps.test_score:.2f} safety={ps.safety_score:.2f} "
            f"cov_delta={ps.coverage_delta:+.2f}"
        )
        return ps

    def rank(self, scores: List[PatchScore]) -> List[PatchScore]:
        """Return *scores* sorted by descending total."""
        return sorted(scores, key=lambda s: s.total, reverse=True)
