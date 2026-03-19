from typing import Any, Dict

from aae.analysis.symbolic_constraints import ConstraintEngine

_ALLOWED_TYPES = {"patch", "refactor", "config"}
_ALLOWED_RISKS = {"low", "medium", "high"}

_engine = ConstraintEngine()


def validate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    if candidate.get("type") not in _ALLOWED_TYPES:
        return {"valid": False, "reason": "invalid_type"}

    if candidate.get("risk") not in _ALLOWED_RISKS:
        return {"valid": False, "reason": "invalid_risk"}

    if candidate.get("confidence", 0.0) < 0.3:
        return {"valid": False, "reason": "low_confidence"}

    if not candidate.get("diff", "").strip():
        return {"valid": False, "reason": "empty_diff"}

    if not isinstance(candidate.get("target_files", []), list):
        return {"valid": False, "reason": "invalid_target_files"}

    if not _engine.validate_patch_safety(candidate):
        return {"valid": False, "reason": "unsafe_patch"}

    return {"valid": True, "reason": None}
