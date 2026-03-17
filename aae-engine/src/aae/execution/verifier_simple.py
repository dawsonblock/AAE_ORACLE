class VerifierSimple:
    def verify(self, command, result):
        issues = []

        if command["type"] in {"test", "shell"} and result.get("exit_code", 1) != 0:
            issues.append("command_failed")

        if command["type"] == "patch" and not result.get("applied", False):
            issues.append("patch_not_applied")

        return {
            "ok": len(issues) == 0,
            "issues": issues,
            "details": result,
        }
