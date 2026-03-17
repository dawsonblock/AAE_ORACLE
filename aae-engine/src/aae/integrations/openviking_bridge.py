from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List


class OpenVikingBridge:
    """Structured L2 context store inspired by OpenViking's category model."""

    CATEGORIES = ('profile', 'preferences', 'entities', 'events', 'cases', 'patterns', 'artifacts')

    def __init__(self, root: str | Path = 'artifacts/openviking_context') -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for category in self.CATEGORIES:
            (self.root / category).mkdir(parents=True, exist_ok=True)

    def _slug(self, value: str) -> str:
        clean = re.sub(r'[^a-zA-Z0-9_-]+', '-', value.strip()).strip('-').lower()
        return clean or 'item'

    def store_memory(self, category: str, title: str, content: str, metadata: Dict[str, Any] | None = None) -> Path:
        if category not in self.CATEGORIES:
            raise ValueError(f'unsupported category: {category}')
        payload = {
            'title': title,
            'content': content,
            'metadata': metadata or {},
            'created_at': time.time(),
            'category': category,
        }
        path = self.root / category / f"{int(time.time() * 1000)}-{self._slug(title)}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
        return path

    def store_artifact(self, task_id: str, artifact: Dict[str, Any]) -> Path:
        title = artifact.get('artifact_id', task_id)
        return self.store_memory('artifacts', title, artifact.get('content', ''), {'task_id': task_id, **artifact})

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        q = query.lower().strip()
        hits: List[Dict[str, Any]] = []
        for path in self.root.rglob('*.json'):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except Exception:
                continue
            hay = json.dumps(payload, sort_keys=True).lower()
            if q and q not in hay:
                continue
            score = hay.count(q) if q else 1
            hits.append({
                'source': 'openviking_l2',
                'title': payload.get('title', path.stem),
                'content': payload.get('content', ''),
                'metadata': {'path': str(path), **payload.get('metadata', {})},
                'score': float(score),
            })
        hits.sort(key=lambda x: x['score'], reverse=True)
        return hits[:limit]

    def tree_summary(self) -> Dict[str, int]:
        return {category: len(list((self.root / category).glob('*.json'))) for category in self.CATEGORIES}
