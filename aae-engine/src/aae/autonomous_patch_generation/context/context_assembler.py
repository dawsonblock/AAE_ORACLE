"""autonomous_patch_generation/context/context_assembler — assemble context."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_MAX_TOKENS = 8000   # conservative budget for patch context


@dataclass
class PatchContext:
    """Assembled context required to generate a patch."""

    goal: str
    target_files: List[str] = field(default_factory=list)
    file_contents: Dict[str, str] = field(default_factory=dict)
    symbols: Dict[str, Any] = field(default_factory=dict)
    failing_tests: List[str] = field(default_factory=list)
    error_message: str = ""
    related_code: List[str] = field(default_factory=list)
    token_count: int = 0

    def to_prompt(self) -> str:
        """Render this context as a prompt string (delegates to assembler)."""
        parts = [f"Goal: {self.goal}\n"]
        if self.error_message:
            parts.append(f"Error: {self.error_message}\n")
        if self.failing_tests:
            tests = "\n".join(f"  - {t}" for t in self.failing_tests)
            parts.append(f"Failing tests:\n{tests}\n")
        for path, content in self.file_contents.items():
            parts.append(f"\n### {path}\n```python\n{content}\n```")
        return "\n".join(parts)


class ContextAssembler:
    """Assemble a :class:`PatchContext` from raw inputs.

    Parameters
    ----------
    repo_root:
        Root of the repository being patched.
    max_tokens:
        Approximate upper bound on total context tokens.
    """

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        max_tokens: int = _MAX_TOKENS,
        token_budget: Optional[int] = None,   # alias for max_tokens
    ) -> None:
        self._root = repo_root or Path(".")
        self._max_tokens = token_budget if token_budget is not None else max_tokens

    def build(
        self,
        goal: str,
        file_paths: Optional[List[str]] = None,
        target_files: Optional[List[str]] = None,
        **kwargs,
    ) -> PatchContext:
        """Alias for :meth:`assemble` accepting *file_paths* as a kwarg."""
        files = file_paths or target_files or []
        return self.assemble(goal=goal, target_files=files, **kwargs)

    def assemble(
        self,
        goal: str,
        target_files: List[str],
        failing_tests: Optional[List[str]] = None,
        error_message: str = "",
        extra_symbols: Optional[Dict[str, Any]] = None,
    ) -> PatchContext:
        """Build a :class:`PatchContext` for *goal*."""
        ctx = PatchContext(
            goal=goal,
            target_files=target_files,
            failing_tests=failing_tests or [],
            error_message=error_message,
            symbols=extra_symbols or {},
        )
        token_budget = self._max_tokens
        for rel_path in target_files:
            abs_path = self._root / rel_path
            try:
                content = abs_path.read_text(encoding="utf-8", errors="replace")
                words = len(content.split())
                if words > token_budget:
                    # Trim to budget
                    content = " ".join(content.split()[:token_budget])
                    words = token_budget
                ctx.file_contents[rel_path] = content
                token_budget -= words
                ctx.token_count += words
                if token_budget <= 0:
                    break
            except FileNotFoundError:
                log.warning("Target file not found: %s", abs_path)
            except Exception as exc:
                log.warning("Failed to read %s: %s", rel_path, exc)
        return ctx

    def to_prompt(self, ctx: PatchContext) -> str:
        """Render *ctx* as a prompt string for a patch-generation model."""
        parts = [f"Goal: {ctx.goal}\n"]
        if ctx.error_message:
            parts.append(f"Error: {ctx.error_message}\n")
        if ctx.failing_tests:
            tests = "\n".join(f"  - {t}" for t in ctx.failing_tests)
            parts.append(f"Failing tests:\n{tests}\n")
        for path, content in ctx.file_contents.items():
            parts.append(f"\n### {path}\n```python\n{content}\n```")
        return "\n".join(parts)
