from __future__ import annotations

from typing import Any

from aae.analysis.symbolic_constraints import ConstraintEngine

_engine = ConstraintEngine()


def validate(candidate: Any) -> bool:
    """Validate a repair candidate before execution.

    Returns True only if the candidate passes both confidence and
    structural safety checks.
    """
    if getattr(candidate, "confidence", 1.0) < 0.3:
        return False

    if not _engine.validate_patch_safety(candidate):
        return False

    return True


__all__ = ["validate"]
