import tempfile
import subprocess
import shutil
from aae.runtime.workspace import RepoMaterializer


class IsolatedWorkspace:
    def __init__(self):
        # Use the shared RepoMaterializer so workspace materialization
        # behavior is consistent across the runtime.
        self._repo_materializer = RepoMaterializer()

    def create(self, repo_path: str):
        """
        Materialize a workspace for the given repository path or URL
        using the shared RepoMaterializer implementation.
        """
        return self._repo_materializer.materialize(repo_path)

    def cleanup(self, workspace_path: str):
        shutil.rmtree(workspace_path, ignore_errors=True)
