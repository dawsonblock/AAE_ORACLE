# EXPERIMENTAL - NOT USED IN SUPPORTED RUNTIME

from aae.execution.sandbox_adapter import SandboxAdapter
from aae.execution.verifier import Verifier
from aae.execution.isolated_workspace import IsolatedWorkspace


class Executor:
    def __init__(self):
        self.sandbox = SandboxAdapter()
        self.verifier = Verifier()
        self.workspace = IsolatedWorkspace()

    def execute(self, command):
        repo = command["repo"]
        workspace = self.workspace.create(repo)

        try:
            local_command = dict(command)
            local_command["repo"] = workspace
            result = self.sandbox.run(local_command)

            verification = self.verifier.verify(local_command, result)

            return {
                "workspace": workspace,
                "result": result,
                "verified": verification.get("ok", True),
                "issues": verification.get("issues", []),
            }
        finally:
            self.workspace.cleanup(workspace)
