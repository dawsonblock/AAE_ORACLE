# EXPERIMENTAL - NOT USED IN SUPPORTED RUNTIME

from aae.patching.git_ops.git_patch_applier import GitPatchApplier


class PatchEngine:
    def __init__(self) -> None:
        self._git_patch_applier = GitPatchApplier()

    def apply_patch(self, repo_path: str, patch_text: str):
        result = self._git_patch_applier.apply_patch(
            repo_path=repo_path,
            patch_text=patch_text,
        )

        if isinstance(result, dict):
            return {
                "applied": result.get("applied", False),
                "stdout": result.get("stdout", ""),
                "stderr": result.get("stderr", ""),
                "exit_code": result.get("exit_code", 0),
                **{
                    k: v
                    for k, v in result.items()
                    if k not in {"applied", "stdout", "stderr", "exit_code"}
                },
            }

        return result
