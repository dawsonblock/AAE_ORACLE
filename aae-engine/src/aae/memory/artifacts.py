from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class ArtifactStore:
    def __init__(self, root: str = "artifacts") -> None:
        self.root = Path(root)
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
