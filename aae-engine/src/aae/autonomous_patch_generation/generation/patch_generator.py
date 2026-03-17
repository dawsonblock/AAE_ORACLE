"""autonomous_patch_generation/generation/patch_generator — generate patches."""
from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class GeneratedPatch:
    """A generated unified diff patch."""

    patch_id: str
    diff: str                   # unified diff text
    target_files: List[str] = field(default_factory=list)
    description: str = ""
    strategy: str = "direct"   # "direct" | "template" | "model"
    confidence: float = 0.5


class PatchGenerator:
    """Generate code patches from a :class:`PatchContext`.

    Strategies
    ----------
    * ``direct`` — apply a pre-composed fix directly (for known patterns)
    * ``template`` — fill a fix template from the context
    * ``model`` — delegate to an LLM (stub; integrate at orchestration layer)
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self._model = model
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"PATCH-{self._counter:04d}"

    def generate(self, ctx, strategy: str = "direct") -> Optional[GeneratedPatch]:
        """Generate a patch for the given :class:`PatchContext`."""
        if strategy == "direct":
            return self._direct(ctx)
        if strategy == "template":
            return self._template(ctx)
        log.warning("Unknown patch strategy: %s", strategy)
        return None

    def generate_from_diff(
        self,
        original: str,
        modified: str,
        filename: str = "file.py",
        description: str = "",
    ) -> GeneratedPatch:
        """Create a patch from *original* and *modified* file content."""
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                modified.splitlines(keepends=True),
                fromfile=f"a/{filename}",
                tofile=f"b/{filename}",
                lineterm="",
            )
        )
        return GeneratedPatch(
            patch_id=self._next_id(),
            diff=diff,
            target_files=[filename],
            description=description,
            strategy="direct",
            confidence=0.9,
        )

    def apply(self, patch: GeneratedPatch, root: Path) -> bool:
        """Apply *patch* to the filesystem under *root*.

        Uses ``patch`` CLI if available; falls back to Python difflib apply.
        Returns ``True`` on success.
        """
        try:
            import subprocess
            result = subprocess.run(
                ["patch", "-p1", "--dry-run"],
                input=patch.diff,
                capture_output=True,
                text=True,
                cwd=str(root),
                timeout=15,
            )
            if result.returncode != 0:
                log.warning("Dry-run patch failed: %s", result.stderr[:200])
                return False
            subprocess.run(
                ["patch", "-p1"],
                input=patch.diff,
                text=True,
                cwd=str(root),
                timeout=15,
                check=True,
            )
            return True
        except FileNotFoundError:
            # patch CLI not available — attempt Python apply
            return self._python_apply(patch, root)
        except Exception as exc:
            log.error("Patch apply error: %s", exc)
            return False

    def _direct(self, ctx) -> Optional[GeneratedPatch]:
        # Stub: in production, a real model call goes here
        return GeneratedPatch(
            patch_id=self._next_id(),
            diff="",
            target_files=ctx.target_files,
            description=ctx.goal,
            strategy="direct",
            confidence=0.3,
        )

    def _template(self, ctx) -> Optional[GeneratedPatch]:
        return self._direct(ctx)  # same stub

    @staticmethod
    def _python_apply(patch: GeneratedPatch, root: Path) -> bool:
        """Very basic unified-diff applier for single-file patches."""
        try:
            lines = patch.diff.splitlines()
            target: Optional[str] = None
            for line in lines:
                if line.startswith("+++ b/"):
                    target = line[6:]
                    break
            if not target:
                return False
            path = root / target
            original = path.read_text(encoding="utf-8").splitlines(keepends=True)
            result = list(
                difflib.restore(
                    patch.diff.splitlines(keepends=True), 2
                )
            )
            path.write_text("".join(result), encoding="utf-8")
            return True
        except Exception as exc:
            log.error("Python patch apply failed: %s", exc)
            return False
