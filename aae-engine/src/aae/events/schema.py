from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time
import uuid


@dataclass
class Event:
    type: str
    task_id: str
    repo_id: str
    agent_id: str
    payload: Dict[str, Any]
    parent_agent_id: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
