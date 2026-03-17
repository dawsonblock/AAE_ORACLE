"""tool_registry — central registry of all tools available to agents.

Tools are typed callables or coroutines that agents invoke through
``ToolRouter``.  This registry maps tool names to their metadata and
validator/handler pairs so that the router can resolve them at runtime.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """Metadata describing a single tool."""

    name: str
    description: str
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    requires_capability: bool = False
    handler: Optional[Callable[..., Any]] = field(
        default=None, repr=False
    )

    def validate_payload(self, payload: Dict[str, Any]) -> List[str]:
        """Return list of missing required params."""
        return [p for p in self.required_params if p not in payload]


class ToolRegistry:
    """Global registry for agent tools.

    Usage::

        registry = ToolRegistry()
        registry.register(ToolSpec(
            name="run_tests",
            description="Execute test suite via sandbox.",
            required_params=["test_ids"],
            requires_capability=True,
            handler=some_async_fn,
        ))
        spec = registry.get("run_tests")
    """

    _BUILTIN_SPECS: List[ToolSpec] = [
        ToolSpec(
            name="run_tests",
            description="Execute a set of pytest test IDs via sandbox.",
            required_params=["test_ids"],
            requires_capability=True,
        ),
        ToolSpec(
            name="run_code",
            description="Execute a Python code snippet.",
            required_params=["code"],
            optional_params=["language"],
            requires_capability=True,
        ),
        ToolSpec(
            name="sandbox_exec",
            description="Run an arbitrary shell command in isolation.",
            required_params=["command"],
            optional_params=["image"],
            requires_capability=True,
        ),
        ToolSpec(
            name="memory_read",
            description="Semantic search over agent memory.",
            required_params=["query"],
            optional_params=["k"],
            requires_capability=False,
        ),
        ToolSpec(
            name="memory_write",
            description="Store a key-value pair in agent memory.",
            required_params=["key", "value"],
            optional_params=["metadata"],
            requires_capability=False,
        ),
        ToolSpec(
            name="search",
            description="Search the repository / web for relevant info.",
            required_params=["query"],
            optional_params=["k"],
            requires_capability=False,
        ),
        ToolSpec(
            name="log",
            description="Emit a structured log message.",
            required_params=["message"],
            requires_capability=False,
        ),
    ]

    def __init__(self) -> None:
        self._specs: Dict[str, ToolSpec] = {}
        for spec in self._BUILTIN_SPECS:
            self._specs[spec.name] = spec

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def register(self, spec: ToolSpec, overwrite: bool = False) -> None:
        if spec.name in self._specs and not overwrite:
            raise ValueError(
                f"Tool '{spec.name}' already registered."
                " Pass overwrite=True to replace."
            )
        self._specs[spec.name] = spec
        log.debug("tool registered: %s", spec.name)

    def unregister(self, name: str) -> bool:
        if name in self._specs:
            del self._specs[name]
            return True
        return False

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._specs.get(name)

    def require(self, name: str) -> ToolSpec:
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"Tool '{name}' not found in registry.")
        return spec

    # ── listing ───────────────────────────────────────────────────────────────

    def all_names(self) -> List[str]:
        return sorted(self._specs.keys())

    def gated(self) -> List[str]:
        """Return names of tools that require capability declaration."""
        return [n for n, s in self._specs.items() if s.requires_capability]

    def public(self) -> List[str]:
        return [n for n, s in self._specs.items() if not s.requires_capability]

    def to_dict(self) -> Dict[str, Any]:
        return {
            name: {
                "description": s.description,
                "required_params": s.required_params,
                "optional_params": s.optional_params,
                "gated": s.requires_capability,
            }
            for name, s in self._specs.items()
        }

    # ── validation ────────────────────────────────────────────────────────────

    def validate_call(
        self, name: str, payload: Dict[str, Any]
    ) -> List[str]:
        """Return list of validation error strings (empty = valid)."""
        spec = self.get(name)
        if spec is None:
            return [f"Unknown tool: '{name}'"]
        missing = spec.validate_payload(payload)
        if missing:
            return [f"Missing required params: {missing}"]
        return []


# Module-level singleton so the router can import it without DI
default_registry = ToolRegistry()
