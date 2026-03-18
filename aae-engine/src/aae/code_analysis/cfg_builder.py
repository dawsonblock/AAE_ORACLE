from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CfgSummary:
    cfg_nodes: List[Any] = field(default_factory=list)
    branch_points: List[Any] = field(default_factory=list)


class CfgBuilder:
    """Builds control-flow graphs from source code ASTs."""

    def build(self, source: str) -> Dict[str, Any]:
        return {"nodes": [], "edges": []}

    def build_from_file(self, file_path: str) -> Dict[str, Any]:
        return {"nodes": [], "edges": []}

    def build_for_symbol(
        self,
        repo_path: Optional[str] = None,
        file_path: Optional[str] = None,
        symbol_id: Optional[str] = None,
        qualname: Optional[str] = None,
        **kwargs: Any,
    ) -> CfgSummary:
        return CfgSummary()


__all__ = ["CfgBuilder", "CfgSummary"]
