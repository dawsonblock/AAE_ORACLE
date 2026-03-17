"""monitoring/metrics_collector — in-process Prometheus-compatible metrics.

Collects counters, gauges, and histograms for all AAE subsystems.
Exports them as Prometheus text format so ``/v1/metrics`` can serve them.

Falls back gracefully when ``prometheus_client`` is not installed.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def _try_prometheus() -> Optional[Any]:
    try:
        import prometheus_client  # type: ignore[import]
        return prometheus_client
    except ImportError:
        return None


class MetricsCollector:
    """Collect and export metrics for the AAE runtime.

    When ``prometheus_client`` is available metrics are exposed as real
    Prometheus objects.  Otherwise a lightweight dict-based fallback is
    used so the rest of the system never needs to check for the library.
    """

    def __init__(self, namespace: str = "aae") -> None:
        self._ns = namespace
        self._prom = _try_prometheus()
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._prom_counters: Dict[str, Any] = {}
        self._prom_gauges: Dict[str, Any] = {}
        self._prom_histograms: Dict[str, Any] = {}
        self._start_time = time.time()

    # ── counter ───────────────────────────────────────────────────────────────

    def inc(self, name: str, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter."""
        key = self._key(name, labels)
        self._counters[key] += amount
        if self._prom:
            c = self._prom_counter(name)
            c.inc(amount)

    def counter_value(self, name: str) -> float:
        return self._counters.get(self._key(name, None), 0.0)

    # ── gauge ─────────────────────────────────────────────────────────────────

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge to *value*."""
        self._gauges[name] = value
        if self._prom:
            g = self._prom_gauge(name)
            g.set(value)

    def inc_gauge(self, name: str, amount: float = 1.0) -> None:
        self._gauges[name] = self._gauges.get(name, 0.0) + amount
        if self._prom:
            self._prom_gauge(name).inc(amount)

    def dec_gauge(self, name: str, amount: float = 1.0) -> None:
        self._gauges[name] = self._gauges.get(name, 0.0) - amount
        if self._prom:
            self._prom_gauge(name).dec(amount)

    # ── histogram ─────────────────────────────────────────────────────────────

    def observe(self, name: str, value: float) -> None:
        """Record a single histogram observation."""
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 10_000:
            self._histograms[name] = self._histograms[name][-5_000:]
        if self._prom:
            h = self._prom_histogram(name)
            h.observe(value)

    def histogram_p(self, name: str, pct: float) -> float:
        """Approximate *pct*-th percentile (0-100) for a histogram."""
        values = sorted(self._histograms.get(name, []))
        if not values:
            return 0.0
        idx = max(0, int(len(values) * pct / 100) - 1)
        return values[idx]

    # ── export ────────────────────────────────────────────────────────────────

    def export_text(self) -> str:
        """Emit Prometheus text format if available, else a simple dump."""
        if self._prom:
            try:
                from prometheus_client import generate_latest  # type: ignore[import]
                return generate_latest().decode()
            except Exception:
                pass
        lines = [f"# AAE metrics snapshot  uptime={time.time() - self._start_time:.1f}s"]
        for k, v in sorted(self._counters.items()):
            lines.append(f"{k} {v}")
        for k, v in sorted(self._gauges.items()):
            lines.append(f"{k} {v}")
        return "\n".join(lines) + "\n"

    def snapshot(self) -> Dict[str, Any]:
        """Return a dict summary of all metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: {
                    "count": len(v),
                    "p50": self.histogram_p(k, 50),
                    "p95": self.histogram_p(k, 95),
                    "p99": self.histogram_p(k, 99),
                }
                for k, v in self._histograms.items()
            },
        }

    # ── internal ──────────────────────────────────────────────────────────────

    def _key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        if labels:
            lbl = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{self._ns}_{name}{{{lbl}}}"
        return f"{self._ns}_{name}"

    def _prom_counter(self, name: str) -> Any:
        full = f"{self._ns}_{name}"
        if full not in self._prom_counters:
            self._prom_counters[full] = self._prom.Counter(  # type: ignore[union-attr]
                full, f"AAE counter: {name}"
            )
        return self._prom_counters[full]

    def _prom_gauge(self, name: str) -> Any:
        full = f"{self._ns}_{name}"
        if full not in self._prom_gauges:
            self._prom_gauges[full] = self._prom.Gauge(  # type: ignore[union-attr]
                full, f"AAE gauge: {name}"
            )
        return self._prom_gauges[full]

    def _prom_histogram(self, name: str) -> Any:
        full = f"{self._ns}_{name}"
        if full not in self._prom_histograms:
            self._prom_histograms[full] = self._prom.Histogram(  # type: ignore[union-attr]
                full, f"AAE histogram: {name}"
            )
        return self._prom_histograms[full]
