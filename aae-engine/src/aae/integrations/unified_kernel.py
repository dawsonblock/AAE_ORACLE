from __future__ import annotations

from typing import Dict, Any


class UnifiedKernel:
    """Canonical routing surface for the deeply integrated stack."""

    TOOL_MAP = {
        'research': 'deep_research',
        'security': 'sec_af',
        'engineering': 'swe_af',
        'memory': 'memory_fabric',
        'general': 'general_executor',
    }

    def decide(self, objective: str, preferred_tool: str | None = None) -> Dict[str, Any]:
        if preferred_tool:
            return {'lane': 'preferred', 'tool': preferred_tool, 'reason': 'preferred tool requested'}
        lowered = objective.lower()
        if any(x in lowered for x in ('research', 'investigate', 'analyze', 'summarize')):
            lane = 'research'
        elif any(x in lowered for x in ('security', 'scan', 'audit', 'vulnerability')):
            lane = 'security'
        elif any(x in lowered for x in ('fix', 'patch', 'build', 'implement', 'refactor')):
            lane = 'engineering'
        elif any(x in lowered for x in ('remember', 'recall', 'context')):
            lane = 'memory'
        else:
            lane = 'general'
        return {'lane': lane, 'tool': self.TOOL_MAP[lane], 'reason': f'objective routed to {lane} lane'}
