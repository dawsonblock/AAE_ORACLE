import os
import tempfile
import subprocess

from aae.patching.git_ops.git_patch_applier import GitPatchApplier


class PatchEngine:
    def __init__(self) -> None:
        # Delegate patch application to the centralized GitPatchApplier
        self._git_patch_applier = GitPatchApplier()

    def apply_patch(self, repo_path: str, patch_text: str):
        """
        Apply a patch to the given repository path.

        This delegates to GitPatchApplier so that we inherit existing
        repo-safety checks and consistent behavior.
        """
        result = self._git_patch_applier.apply_patch(
            repo_path=repo_path,
            patch_text=patch_text,
        )

        # Preserve the original return structure for callers that expect it.
        if isinstance(result, dict):
            return {
                "applied": result.get("applied", False),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code", 0),
                # Any additional keys from GitPatchApplier are retained.
                **{k: v for k, v in result.items() if k not in {
                    "applied", "stdout", "stderr", "exit_code"
                }},
            }

        # Fallback: if GitPatchApplier returns a non-dict type, just forward it.
        return result
