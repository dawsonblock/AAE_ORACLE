"""monitoring/cost_monitor — token and compute cost tracking.

Tracks LLM token usage, sandbox CPU seconds, and translates them into
estimated monetary cost so operators can monitor spend per workflow/agent.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Default USD cost per 1 000 tokens (approximate, configurable)
_DEFAULT_INPUT_COST = 0.005   # e.g. GPT-4o input
_DEFAULT_OUTPUT_COST = 0.015  # e.g. GPT-4o output
_DEFAULT_COMPUTE_COST = 0.0001  # per CPU-second


@dataclass
class TokenUsage:
    """Record for a single LLM call."""

    agent: str
    workflow_id: str
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: float = field(default_factory=time.time)

    def cost_usd(
        self,
        input_rate: float = _DEFAULT_INPUT_COST,
        output_rate: float = _DEFAULT_OUTPUT_COST,
    ) -> float:
        return (
            self.input_tokens * input_rate / 1000
            + self.output_tokens * output_rate / 1000
        )


@dataclass
class ComputeUsage:
    """Record for a single sandbox execution."""

    workflow_id: str
    cpu_seconds: float
    timestamp: float = field(default_factory=time.time)

    def cost_usd(self, rate: float = _DEFAULT_COMPUTE_COST) -> float:
        return self.cpu_seconds * rate


class CostMonitor:
    """Accumulate and report cost metrics across the AAE runtime.

    Parameters
    ----------
    input_cost_per_1k:
        USD per 1 000 input tokens.
    output_cost_per_1k:
        USD per 1 000 output tokens.
    compute_cost_per_cpu_second:
        USD per CPU-second of sandbox usage.
    budget_alert_threshold:
        Log a warning when cumulative cost exceeds this USD value.
    """

    def __init__(
        self,
        input_cost_per_1k: float = _DEFAULT_INPUT_COST,
        output_cost_per_1k: float = _DEFAULT_OUTPUT_COST,
        compute_cost_per_cpu_second: float = _DEFAULT_COMPUTE_COST,
        budget_alert_threshold: Optional[float] = None,
    ) -> None:
        self._input_rate = input_cost_per_1k
        self._output_rate = output_cost_per_1k
        self._compute_rate = compute_cost_per_cpu_second
        self._budget = budget_alert_threshold
        self._token_log: List[TokenUsage] = []
        self._compute_log: List[ComputeUsage] = []
        # Per-workflow cost accumulator
        self._wf_cost: Dict[str, float] = defaultdict(float)
        self._total_cost: float = 0.0

    # ── record ────────────────────────────────────────────────────────────────

    def record_tokens(
        self,
        agent: str,
        workflow_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Record token usage and return the incremental cost in USD."""
        usage = TokenUsage(
            agent=agent,
            workflow_id=workflow_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        cost = usage.cost_usd(self._input_rate, self._output_rate)
        self._token_log.append(usage)
        self._accumulate(workflow_id, cost)
        return cost

    def record_compute(
        self, workflow_id: str, cpu_seconds: float
    ) -> float:
        """Record compute usage and return the incremental cost in USD."""
        usage = ComputeUsage(
            workflow_id=workflow_id, cpu_seconds=cpu_seconds
        )
        cost = usage.cost_usd(self._compute_rate)
        self._compute_log.append(usage)
        self._accumulate(workflow_id, cost)
        return cost

    # ── query ─────────────────────────────────────────────────────────────────

    def workflow_cost(self, workflow_id: str) -> float:
        return self._wf_cost.get(workflow_id, 0.0)

    def total_cost(self) -> float:
        return self._total_cost

    def token_summary(self) -> Dict[str, Any]:
        total_in = sum(u.input_tokens for u in self._token_log)
        total_out = sum(u.output_tokens for u in self._token_log)
        return {
            "calls": len(self._token_log),
            "input_tokens": total_in,
            "output_tokens": total_out,
            "cost_usd": (
                total_in * self._input_rate / 1000
                + total_out * self._output_rate / 1000
            ),
        }

    def recent_calls(self, n: int = 20) -> List[Dict[str, Any]]:
        return [
            {
                "agent": u.agent,
                "workflow_id": u.workflow_id,
                "model": u.model,
                "tokens": u.input_tokens + u.output_tokens,
                "cost_usd": u.cost_usd(self._input_rate, self._output_rate),
                "ts": u.timestamp,
            }
            for u in self._token_log[-n:]
        ]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "total_cost_usd": self._total_cost,
            "workflow_costs": dict(self._wf_cost),
            "tokens": self.token_summary(),
            "compute_calls": len(self._compute_log),
        }

    # ── internal ──────────────────────────────────────────────────────────────

    def _accumulate(self, workflow_id: str, cost: float) -> None:
        self._wf_cost[workflow_id] += cost
        self._total_cost += cost
        if self._budget and self._total_cost >= self._budget:
            log.warning(
                "cost budget exceeded: total=%.4f USD threshold=%.4f",
                self._total_cost,
                self._budget,
            )


class DashboardServer:
    """Minimal HTTP dashboard server exposing cost + metrics data.

    In production this role is fulfilled by Grafana.  This class exists
    so developers can spin up a quick inspection endpoint without external
    dependencies.
    """

    def __init__(
        self,
        cost_monitor: Optional[CostMonitor] = None,
        metrics_collector: Any | None = None,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        self._cost = cost_monitor
        self._metrics = metrics_collector
        self.host = host
        self.port = port

    async def start(self) -> None:
        log.info(
            "DashboardServer starting at http://%s:%d", self.host, self.port
        )
        try:
            from aae.gateway.api_server import build_app

            import uvicorn  # type: ignore[import]
            app = build_app(
                metrics_collector=self._metrics,
            )
            config = uvicorn.Config(
                app, host=self.host, port=self.port, log_level="warning"
            )
            await uvicorn.Server(config).serve()
        except Exception as exc:
            log.error("DashboardServer failed to start: %s", exc)
