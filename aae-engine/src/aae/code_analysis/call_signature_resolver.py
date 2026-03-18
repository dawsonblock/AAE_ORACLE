from __future__ import annotations

from typing import Any, Dict, List, Optional


class CallSignatureResolver:
    """Resolves call signatures for functions/methods in a codebase."""

    def resolve(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"signature": "", "resolved_calls": [], "resolved": False}

    def resolve_all(self, names: List[str], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return [{"name": name, "signature": "", "resolved_calls": [], "resolved": False} for name in names]


__all__ = ["CallSignatureResolver"]
