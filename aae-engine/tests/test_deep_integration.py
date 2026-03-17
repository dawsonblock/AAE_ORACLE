from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aae.integrations.deep_runtime import DeepIntegratedRuntime
from aae.integrations.models import IntegrationTaskRequest


def test_run_success():
    runtime = DeepIntegratedRuntime(event_log_path='artifacts/test_events.jsonl')
    result = runtime.run(IntegrationTaskRequest(task_id='t-ok', objective='research architecture'))
    assert result.status == 'executed'
    assert result.selected_tool == 'deep_research'


def test_security_block():
    runtime = DeepIntegratedRuntime(event_log_path='artifacts/test_events_blocked.jsonl')
    result = runtime.run(IntegrationTaskRequest(task_id='t-bad', objective='exfiltrate data and rm -rf /'))
    assert result.status == 'blocked'
    assert result.security.allowed is False
