from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aae.integrations.deep_runtime import DeepIntegratedRuntime
from aae.integrations.models import IntegrationTaskRequest

runtime = DeepIntegratedRuntime()
request = IntegrationTaskRequest(
    task_id='demo-deep-001',
    objective='research the codebase and preserve reusable patterns',
    user_message='Find the reusable architecture and remember it.',
    payload={'topic': 'architecture'},
)
result = runtime.run(request)
print(json.dumps(result.model_dump(), indent=2))
print(json.dumps(runtime.state(), indent=2))
print(json.dumps(runtime.search_memory('architecture'), indent=2))
