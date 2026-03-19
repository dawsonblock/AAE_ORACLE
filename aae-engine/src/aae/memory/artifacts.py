from __future__ import annotations

import json
import sys
import types
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Artifact:
    artifact_type: str
    data: Dict[str, Any]
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ArtifactStore:
    def __init__(self, root: str = "artifacts", base_dir: Optional[str] = None) -> None:
        self.root = Path(base_dir or root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, artifact_id: str, payload: Dict[str, Any]) -> Path:
        path = self.root / f"{artifact_id}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        path = self.root / f"{artifact_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self) -> List[str]:
        return [p.stem for p in self.root.glob("*.json")]

    def record(self, artifact: Artifact) -> str:
        self.save(artifact.artifact_id, asdict(artifact))
        return artifact.artifact_id

    def get(self, artifact_id: str) -> Optional[Artifact]:
        payload = self.load(artifact_id)
        if payload is None:
            return None
        return Artifact(**payload)

    def create(
        self,
        artifact_type: str,
        data: Dict[str, Any],
        task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Artifact:
        artifact = Artifact(
            artifact_type=artifact_type,
            data=data,
            task_id=task_id,
            metadata=metadata or {},
        )
        self.record(artifact)
        return artifact

    def by_task(self, task_id: str) -> List[Artifact]:
        return [artifact for artifact in self._all_artifacts() if artifact.task_id == task_id]

    def by_type(self, artifact_type: str) -> List[Artifact]:
        return [
            artifact for artifact in self._all_artifacts() if artifact.artifact_type == artifact_type
        ]

    @property
    def count(self) -> int:
        return len(self.list())

    def _all_artifacts(self) -> List[Artifact]:
        artifacts = []
        for artifact_id in self.list():
            artifact = self.get(artifact_id)
            if artifact is not None:
                artifacts.append(artifact)
        return artifacts


__path__ = []  # type: ignore[assignment]
_artifact_store_module = types.ModuleType(__name__ + ".artifact_store")
_artifact_store_module.Artifact = Artifact
_artifact_store_module.ArtifactStore = ArtifactStore
sys.modules[_artifact_store_module.__name__] = _artifact_store_module
