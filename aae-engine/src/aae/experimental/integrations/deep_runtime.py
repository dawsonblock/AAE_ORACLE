from __future__ import annotations

import time
from typing import Any, Dict, List

from aae.core.event_log import EventLog
from aae.execution.executor import ActionSpec, Executor
from aae.execution.sandbox import ExecutionSandbox, SandboxConfig
from aae.execution.verifier import Verifier
from aae.memory.in_memory import InMemoryMemoryStore
from aae.integrations.agentshield_bridge import AgentShieldBridge
from aae.integrations.distributed_runtime import DistributedRuntime
from aae.integrations.memory_fabric import MemoryFabric
from aae.integrations.models import IntegrationRunResult, IntegrationTaskRequest
from aae.integrations.unified_kernel import UnifiedKernel


class DeepIntegratedRuntime:
    """AAE-native runtime that composes AAE execution with OpenViking, SimpleMem, and AgentShield patterns."""

    def __init__(self, event_log_path: str = 'artifacts/deep_runtime_events.jsonl') -> None:
        self.event_log = EventLog(log_path=event_log_path)
        self.executor = Executor(
            sandbox=ExecutionSandbox(SandboxConfig(workdir='.', timeout_seconds=60)),
            verifier=Verifier(),
            event_log=self.event_log,
        )
        self.security = AgentShieldBridge()
        self.memory = MemoryFabric()
        self.kernel = UnifiedKernel()
        self.distributed = DistributedRuntime()
        self.store = InMemoryMemoryStore()
        self._last_result: Dict[str, Any] | None = None

    async def run(self, request: IntegrationTaskRequest) -> IntegrationRunResult:
        started = time.time()
        self.memory.start_session(request.task_id, request.objective, request.user_message)
        self.event_log.create_event('integration.workflow_received', task_id=request.task_id, status='received', payload=request.model_dump())

        security = self.security.scan_payload(request.model_dump())
        self.event_log.create_event('integration.security_scanned', task_id=request.task_id, status='scanned', payload=security.model_dump())
        if not security.allowed:
            blocked = IntegrationRunResult(
                task_id=request.task_id,
                status='blocked',
                selected_tool='none',
                selected_worker='none',
                security=security,
                action_result={'success': False, 'reason': 'blocked by security gate'},
                evaluation={'score': 0.0, 'artifact_count': 0},
                improvement={'action': 'revise_request'},
                memory_summary=self.memory.finalize_session(request.task_id, request.objective, {'status': 'blocked', 'selected_tool': 'none', 'artifacts': []}),
            )
            self._last_result = blocked.model_dump()
            return blocked

        decision = self.kernel.decide(request.objective, request.preferred_tool)
        lane = 'general' if decision['lane'] == 'preferred' else decision['lane']
        worker = self.distributed.pick(lane)
        action = self._build_action(request, decision)
        self.memory.record_system_message(request.task_id, f"selected tool={decision['tool']} lane={decision['lane']}")
        self.memory.record_tool_use(request.task_id, decision['tool'], str(request.payload), f"dispatch via {worker.worker_id}")
        result = await self.executor.run(action)
        self.distributed.complete(worker)

        artifacts = self._make_artifacts(request, decision, result, worker.worker_id, started)
        evaluation = {
            'score': 1.0 if result.success else 0.0,
            'artifact_count': len(artifacts),
            'duration_s': round(time.time() - started, 4),
        }
        improvement = {'action': 'accept' if result.success else 'retry_or_replan'}
        memory_summary = self.memory.finalize_session(
            request.task_id,
            request.objective,
            {'status': 'executed' if result.success else 'failed', 'selected_tool': decision['tool'], 'artifacts': artifacts},
        )
        packaged = IntegrationRunResult(
            task_id=request.task_id,
            status='executed' if result.success else 'failed',
            selected_tool=decision['tool'],
            selected_worker=worker.worker_id,
            security=security,
            action_result={
                'success': result.success,
                'output': result.output,
                'error': result.error,
                'artifacts': result.artifacts,
            },
            evaluation=evaluation,
            improvement=improvement,
            memory_summary=memory_summary,
        )
        self.store.put('integrations', request.task_id, packaged.model_dump())
        self.event_log.create_event('integration.workflow_completed', task_id=request.task_id, status=packaged.status, payload=packaged.model_dump())
        self._last_result = packaged.model_dump()
        return packaged

    def search_memory(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        return self.memory.search(query, limit=limit)

    def state(self) -> Dict[str, Any]:
        return {
            'workers': self.distributed.status(),
            'event_count': self.event_log.count,
            'memory': self.memory.status(),
            'last_result': self._last_result,
        }

    def graph(self) -> Dict[str, Any]:
        return {
            'nodes': [
                {'id': 'dashboard', 'label': 'AAE Dashboard'},
                {'id': 'runtime', 'label': 'DeepIntegratedRuntime'},
                {'id': 'kernel', 'label': 'UnifiedKernel'},
                {'id': 'security', 'label': 'AgentShieldBridge'},
                {'id': 'executor', 'label': 'AAE Executor'},
                {'id': 'simplemem', 'label': 'SimpleMemBridge'},
                {'id': 'openviking', 'label': 'OpenVikingBridge'},
                {'id': 'workers', 'label': 'DistributedRuntime'},
            ],
            'edges': [
                {'source': 'dashboard', 'target': 'runtime', 'relation': 'calls'},
                {'source': 'runtime', 'target': 'kernel', 'relation': 'plans'},
                {'source': 'runtime', 'target': 'security', 'relation': 'preflights'},
                {'source': 'runtime', 'target': 'executor', 'relation': 'executes'},
                {'source': 'runtime', 'target': 'simplemem', 'relation': 'stores_l1'},
                {'source': 'runtime', 'target': 'openviking', 'relation': 'stores_l2'},
                {'source': 'runtime', 'target': 'workers', 'relation': 'dispatches'},
            ],
        }

    def _build_action(self, request: IntegrationTaskRequest, decision: Dict[str, Any]) -> ActionSpec:
        lane = decision['lane']
        if lane == 'engineering':
            action_type = 'apply_patch'
            payload = {'patch': request.payload.get('patch', '# no patch supplied')}
        elif lane == 'security':
            action_type = 'run_tests'
            payload = {'tests': request.payload.get('targets', ['security-scan'])}
        else:
            action_type = 'analyze'
            payload = {'objective': request.objective, **request.payload}
        return ActionSpec(action_id=request.task_id, action_type=action_type, payload=payload)

    def _make_artifacts(self, request: IntegrationTaskRequest, decision: Dict[str, Any], result: Any, worker_id: str, started: float) -> List[Dict[str, Any]]:
        return [
            {
                'artifact_id': f"{request.task_id}-summary",
                'kind': 'runtime_summary',
                'content': f"tool={decision['tool']} worker={worker_id} output={result.output or result.error}",
                'task_id': request.task_id,
                'duration_s': round(time.time() - started, 4),
            }
        ]
