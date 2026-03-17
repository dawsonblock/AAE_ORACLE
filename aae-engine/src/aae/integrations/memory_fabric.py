from __future__ import annotations

from typing import Any, Dict, List

from aae.integrations.openviking_bridge import OpenVikingBridge
from aae.integrations.simplemem_bridge import SimpleMemBridge


class MemoryFabric:
    """Composes L1 episodic and L2 structured memory."""

    def __init__(self) -> None:
        self.l1 = SimpleMemBridge()
        self.l2 = OpenVikingBridge()

    def start_session(self, session_id: str, objective: str, user_message: str = '') -> None:
        self.l1.start_session(session_id, objective)
        if user_message:
            self.l1.record_message(session_id, 'user', user_message)
        self.l2.store_memory('events', f'session-{session_id}-started', objective, {'session_id': session_id})

    def record_user_message(self, session_id: str, content: str) -> None:
        self.l1.record_message(session_id, 'user', content)

    def record_system_message(self, session_id: str, content: str) -> None:
        self.l1.record_message(session_id, 'assistant', content)

    def record_tool_use(self, session_id: str, tool_name: str, input_text: str, output_text: str) -> None:
        self.l1.record_tool_use(session_id, tool_name, input_text, output_text)

    def finalize_session(self, session_id: str, task_objective: str, result: Dict[str, Any]) -> Dict[str, Any]:
        summary = self.l1.finalize_session(session_id)
        self.l2.store_memory('cases', f'case-{session_id}', summary['summary_text'], {
            'session_id': session_id,
            'objective': task_objective,
            'status': result.get('status'),
            'selected_tool': result.get('selected_tool'),
        })
        self.l2.store_memory('patterns', f'pattern-{session_id}', self._derive_pattern(summary, result), {
            'session_id': session_id,
            'selected_tool': result.get('selected_tool'),
        })
        for artifact in result.get('artifacts', []):
            self.l2.store_artifact(session_id, artifact)
        return summary

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        merged = self.l1.search(query, limit=limit) + self.l2.search(query, limit=limit)
        merged.sort(key=lambda x: x.get('score', 0.0), reverse=True)
        return merged[:limit]

    def status(self) -> Dict[str, Any]:
        return {'l2_tree': self.l2.tree_summary()}

    def _derive_pattern(self, summary: Dict[str, Any], result: Dict[str, Any]) -> str:
        return (
            f"When objective resembles '{result.get('selected_tool')}', collect short user intent, "
            f"run a bounded action, and persist artifacts plus a compact summary. "
            f"Observed tool events: {summary.get('tool_event_count', 0)}."
        )
