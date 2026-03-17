from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from aae.integrations.deep_runtime import DeepIntegratedRuntime
from aae.integrations.models import IntegrationTaskRequest

router = APIRouter(prefix='/api/integrations', tags=['integrations'])
RUNTIME = DeepIntegratedRuntime()


@router.get('/health')
async def health():
    return {'status': 'ok', 'engine': 'deep-integrated-runtime'}


@router.post('/run')
async def run_task(request: IntegrationTaskRequest):
    return RUNTIME.run(request).model_dump()


@router.post('/security/scan')
async def security_scan(request: IntegrationTaskRequest):
    return RUNTIME.security.scan_payload(request.model_dump()).model_dump()


@router.get('/memory/search')
async def memory_search(q: str, limit: int = 10):
    return RUNTIME.search_memory(q, limit=limit)


@router.get('/state')
async def state():
    return RUNTIME.state()


@router.get('/graph')
async def graph():
    return RUNTIME.graph()


@router.get('/ui', response_class=HTMLResponse)
async def ui():
    return HTMLResponse('''
    <html><head><title>AAE Deep Integration</title></head>
    <body style="font-family:Arial,sans-serif;max-width:900px;margin:2rem auto;">
      <h1>AAE Deep Integration Runtime</h1>
      <p>Use the API endpoints below:</p>
      <ul>
        <li><code>GET /api/integrations/health</code></li>
        <li><code>POST /api/integrations/run</code></li>
        <li><code>POST /api/integrations/security/scan</code></li>
        <li><code>GET /api/integrations/memory/search?q=...</code></li>
        <li><code>GET /api/integrations/state</code></li>
        <li><code>GET /api/integrations/graph</code></li>
      </ul>
    </body></html>
    ''')
