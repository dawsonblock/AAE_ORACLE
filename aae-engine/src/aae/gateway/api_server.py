"""gateway/api_server — FastAPI application for the AAE public gateway.

Exposes a versioned REST API consumed by the dashboard, CLI tools, and
external integrations.  The server is thin: it validates requests,
delegates to internal subsystems via ``RequestRouter``, and formats
responses.

Endpoints
---------
POST /v1/workflows        → submit a workflow goal
GET  /v1/workflows/{id}   → get workflow status
GET  /v1/health           → liveness/readiness
GET  /v1/metrics          → Prometheus-compatible text metrics
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, PlainTextResponse
    from pydantic import BaseModel

    _FASTAPI_OK = True
except ImportError:
    _FASTAPI_OK = False
    FastAPI = None  # type: ignore[assignment,misc]


if _FASTAPI_OK:
    class WorkflowRequest(BaseModel):
        goal: str
        metadata: Dict[str, Any] = {}

    class WorkflowResponse(BaseModel):
        workflow_id: str
        status: str
        submitted_at: float


def build_app(
    request_router: Any | None = None,
    health_checker: Any | None = None,
    metrics_collector: Any | None = None,
    cors_origins: list[str] | None = None,
) -> Any:
    """Construct and return the FastAPI application.

    Parameters
    ----------
    request_router:
        ``RequestRouter`` instance wired to the controller.
    health_checker:
        ``HealthChecker`` from ``aae.runtime.health_checks``.
    metrics_collector:
        ``MetricsCollector`` from ``aae.monitoring``.
    cors_origins:
        List of allowed CORS origins (default: all).
    """
    if not _FASTAPI_OK:
        raise ImportError("fastapi is required for the gateway API server.")

    app = FastAPI(
        title="AAE Gateway",
        version="2.0.0",
        description="AI Autonomous Engineering — public API gateway",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── routes ─────────────────────────────────────────────────────────────────

    @app.get("/v1/health")
    async def health(request: Request) -> JSONResponse:
        if health_checker:
            result = await health_checker.liveness()
        else:
            result = {"status": "ok", "ts": time.time()}
        return JSONResponse(result)

    @app.get("/v1/ready")
    async def readiness(request: Request) -> JSONResponse:
        if health_checker:
            result = await health_checker.readiness()
            status_code = 200 if result.get("ready") else 503
        else:
            result = {"ready": True}
            status_code = 200
        return JSONResponse(result, status_code=status_code)

    @app.post("/v1/workflows", response_model=WorkflowResponse)
    async def submit_workflow(payload: WorkflowRequest) -> Dict[str, Any]:
        if not request_router:
            raise HTTPException(
                status_code=503, detail="controller not available"
            )
        result = await request_router.submit_workflow(
            goal=payload.goal, metadata=payload.metadata
        )
        return result

    @app.get("/v1/workflows/{workflow_id}")
    async def get_workflow(workflow_id: str) -> JSONResponse:
        if not request_router:
            raise HTTPException(
                status_code=503, detail="controller not available"
            )
        status = await request_router.get_workflow_status(workflow_id)
        if status is None:
            raise HTTPException(
                status_code=404, detail="workflow not found"
            )
        return JSONResponse(status)

    @app.delete("/v1/workflows/{workflow_id}")
    async def cancel_workflow(workflow_id: str) -> JSONResponse:
        if not request_router:
            raise HTTPException(
                status_code=503, detail="controller not available"
            )
        ok = await request_router.cancel_workflow(workflow_id)
        return JSONResponse({"cancelled": ok})

    @app.get("/v1/metrics")
    async def metrics(request: Request) -> PlainTextResponse:
        if metrics_collector:
            text = metrics_collector.export_text()
        else:
            text = "# metrics unavailable\n"
        return PlainTextResponse(text, media_type="text/plain")

    return app


class GatewayServer:
    """Wraps build_app and provides an ``asyncio``-friendly lifecycle.

    Parameters
    ----------
    host / port:
        Bind address for uvicorn.
    All other kwargs are forwarded to ``build_app()``.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        **build_kwargs: Any,
    ) -> None:
        self.host = host
        self.port = port
        self._build_kwargs = build_kwargs
        self._server: Any = None

    async def start(self) -> None:
        try:
            import uvicorn  # type: ignore[import]
        except ImportError:
            log.error("uvicorn is required to run the gateway server")
            return
        app = build_app(**self._build_kwargs)
        config = uvicorn.Config(
            app, host=self.host, port=self.port, log_level="info"
        )
        self._server = uvicorn.Server(config)
        log.info("GatewayServer starting on %s:%d", self.host, self.port)
        await self._server.serve()

    async def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
