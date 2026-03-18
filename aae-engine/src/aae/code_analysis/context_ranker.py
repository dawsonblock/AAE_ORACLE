from __future__ import annotations

from typing import Any, Dict, List, Optional


class ContextRanker:
    """Ranks code context items by relevance to a query."""

    def rank(self, *args: Any, **kwargs: Any) -> Any:
        # Return the third positional argument (graph_context) if provided,
        # otherwise return an empty structure.
        if len(args) >= 3:
            return args[2]
        return {}

    def score(self, item: Dict[str, Any], query: str) -> float:
        return 0.5


__all__ = ["ContextRanker"]
