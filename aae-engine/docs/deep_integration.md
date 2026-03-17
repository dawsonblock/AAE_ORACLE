# Deep Integration Build

This build takes the original AAE umbrella repo and adds a local integration layer that fuses three outside systems at the architecture level:

- **OpenViking** concepts for structured L2 context storage
- **SimpleMem** concepts for SQLite-backed L1 episodic/session memory
- **AgentShield** concepts for pre-execution security scanning and scoring

## What is truly integrated

Inside `src/aae/integrations/`:

- `openviking_bridge.py` stores durable categories and artifacts in a hierarchical filesystem tree
- `simplemem_bridge.py` records session events in SQLite and produces summaries
- `agentshield_bridge.py` scores requests against secrets / permissions / hooks / agent-instruction rules
- `memory_fabric.py` composes L1 + L2 memory and promotes summaries to durable context
- `unified_kernel.py` becomes the single routing surface
- `distributed_runtime.py` assigns work to capability-specific workers
- `deep_runtime.py` binds everything into AAE's own executor, verifier, sandbox, memory store, and event log

## What is not fully fused

This is still not a full dependency-resolved native merge of the upstream repos. Their full codebases are larger and carry their own runtime assumptions.

This build instead does the useful part:

- preserves AAE as the canonical runtime shell
- deeply composes the external systems' memory and security models into that shell
- keeps the final system runnable with only Python dependencies already declared by AAE

## New API endpoints

Run the dashboard with:

```bash
pip install -e .
aae-dashboard
```

Then use:

- `GET /api/integrations/health`
- `POST /api/integrations/run`
- `POST /api/integrations/security/scan`
- `GET /api/integrations/memory/search?q=architecture`
- `GET /api/integrations/state`
- `GET /api/integrations/graph`
- `GET /api/integrations/ui`

## CLI demo

```bash
python scripts/deep_integration_demo.py
python -m aae.runtime.deep_integrated_launcher --objective "security scan the repo"
```
