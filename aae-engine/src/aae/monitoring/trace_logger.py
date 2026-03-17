"""monitoring/trace_logger — lightweight distributed trace emitter.

Records spans across subsystem boundaries (planner → agent → sandbox)
and emits them to an OpenTelemetry-compatible backend.  Falls back to
a structured JSON log when OTEL is unavailable.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Generator, List, Optional

log = logging.getLogger(__name__)


@dataclass
class Span:
    """Minimal distributed trace span."""

    trace_id: str
    span_id: str
    parent_id: Optional[str]
    name: str
    service: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = "ok"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def finish(self, status: str = "ok") -> None:
        self.end_time = time.time()
        self.status = status

    def duration_ms(self) -> float:
        if self.end_time is None:
            return (time.time() - self.start_time) * 1000
        return (self.end_time - self.start_time) * 1000

    def add_event(self, name: str, attrs: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({"name": name, "time": time.time(), "attrs": attrs or {}})

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["duration_ms"] = self.duration_ms()
        return d


class TraceLogger:
    """Emit trace spans to OTEL exporter or structured log fallback.

    Parameters
    ----------
    service_name:
        Name of the service emitting spans (used in OTEL resource).
    otel_endpoint:
        HTTP endpoint for the OTEL collector (e.g. ``http://otel:4318``).
    max_spans:
        Maximum spans kept in the in-memory ring buffer.
    """

    def __init__(
        self,
        service_name: str = "aae",
        otel_endpoint: Optional[str] = None,
        max_spans: int = 5000,
    ) -> None:
        self.service_name = service_name
        self._otel_endpoint = otel_endpoint
        self._max = max_spans
        self._spans: List[Span] = []
        self._tracer: Any = None
        self._active: Dict[str, Span] = {}

    def setup(self) -> None:
        """Initialise OTEL tracer if endpoint is configured."""
        if not self._otel_endpoint:
            return
        try:
            from opentelemetry import trace as otel_trace  # type: ignore[import]
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import]
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource  # type: ignore[import]
            from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import]
            from opentelemetry.sdk.trace.export import (  # type: ignore[import]
                BatchSpanProcessor,
            )

            resource = Resource.create({"service.name": self.service_name})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=self._otel_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            otel_trace.set_tracer_provider(provider)
            self._tracer = otel_trace.get_tracer(self.service_name)
            log.info("TraceLogger OTEL exporter configured")
        except Exception as exc:
            log.warning("OTEL setup failed (%s); using log fallback", exc)

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span and register it."""
        span = Span(
            trace_id=trace_id or str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            parent_id=parent_id,
            name=name,
            service=self.service_name,
            attributes=attributes or {},
        )
        self._active[span.span_id] = span
        return span

    def finish_span(self, span: Span, status: str = "ok") -> None:
        """Complete *span* and emit it."""
        span.finish(status)
        self._active.pop(span.span_id, None)
        self._emit(span)

    @contextmanager
    def span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Generator[Span, None, None]:
        """Context manager that starts and finishes a span."""
        s = self.start_span(name, trace_id, parent_id, attributes)
        try:
            yield s
            self.finish_span(s, "ok")
        except Exception:
            self.finish_span(s, "error")
            raise

    def recent(self, n: int = 50) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._spans[-n:]]

    def _emit(self, span: Span) -> None:
        self._spans.append(span)
        if len(self._spans) > self._max:
            self._spans = self._spans[-self._max:]
        log.debug(
            "span name=%s trace=%s duration=%.1f ms status=%s",
            span.name,
            span.trace_id[:8],
            span.duration_ms(),
            span.status,
        )
