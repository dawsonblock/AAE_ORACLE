# Development Guide

## Architecture Overview

AAE is organized as a layered Python monorepo under `src/aae/`. Each subsystem is a
self-contained package with clear boundaries; cross-subsystem calls go through the
contracts layer (`src/aae/contracts/`) or the runtime services (`src/aae/runtime/services/`).

```
src/aae/
├── adapters/           # Thin wrappers for external agent systems (Deep Research, sec-af, SWE-AF)
├── agents/             # Micro-agent implementations and swarm orchestration
├── autonomous_patch_generation/  # Context assembly, patch generation, simulation, scoring
├── behavior_model/     # CFG building, state-graph, trace collection
├── bug_localization/   # Stack-trace analysis and suspiciousness ranking
├── cluster/            # Worker pool, load balancer, task distributor
├── code_analysis/      # CFG, call-signature, type inference, symbol index
├── contracts/          # Shared Pydantic models (cross-subsystem protocol)
├── controller/         # Main runtime controller, task scheduler, retry policy
├── core/               # Low-level shared utilities (EventLog, ActionGraph)
├── dashboard_api/      # FastAPI server + routers for the web UI
├── evaluation/         # Benchmark runner, experiment evaluator, metrics
├── events/             # Event bus, event store, event replay
├── execution/          # Executor, sandbox, verifier, artifact writer
├── exploration/        # Hypothesis branching and result comparison
├── gateway/            # API key auth, rate limiter, request router
├── graph/              # Call/data-flow/inheritance graph builders, graph store
├── integrations/       # Deep-integration bridges (OpenViking, SimpleMem, AgentShield)
├── learning/           # Trajectory parsing, policy training, reward modelling
├── localization/       # Multi-signal fault localization (spectrum, graph, trace)
├── memory/             # Artifact store, knowledge graph, working memory, vector memory
├── meta/               # Self-improvement loop, strategy optimizer, tool evaluator
├── monitoring/         # Metrics collector, trace logger, dashboard server
├── patching/           # Diff construction, git ops, patch synthesizer
├── persistence/        # PostgreSQL-backed state, trajectory store, graph store
├── planner/            # Action-tree planning, beam search, LLM consensus
├── repository_intelligence/  # RIS: file parsing, symbol/dep extraction, query engine
├── research_engine/    # Document parsing, insight extraction, arxiv/web retrieval
├── runtime/            # Bootstrap, config, workflow presets, system launcher
├── sandbox/            # Docker container management, job scheduling
├── security_analysis/  # Static analysis, attack graph, dependency scan, remediation
├── simulation/         # Dependency impact, risk estimation, test-failure prediction
├── storage/            # Artifact store, Redis store, Postgres store, graph adapters
├── test_repair/        # Counterexample generation, repair guidance, test mutation
└── tools/              # Graph tools registry
```

## Getting Started

```bash
git clone https://github.com/dawsonblock/AAE-ENGINE.git
cd AAE-ENGINE
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
# All unit and end-to-end tests (fast, no external services)
pytest tests/ -q

# Including replay tests
pytest tests/ tests/replay/ -q

# Specific subsystem
pytest tests/unit/test_cluster.py -v
```

## Linting Standards

- **Python**: Follow PEP 8. Max line length 88 (Black-compatible).
- **Imports**: `from __future__ import annotations` at the top of every module.
- **Type hints**: All public functions must be typed.
- **Async**: Use `asyncio`; avoid thread-based concurrency in new code.

## Environment Variables

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | LLM inference (patch generation, consensus) |
| `AAE_DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Optional Redis for event bus / caching |
| `AAE_SANDBOX_IMAGE` | Docker image for sandboxed execution |

Copy `.env.example` to `.env` and fill in your values.

## Adding a New Subsystem

1. Create `src/aae/<subsystem>/__init__.py`.
2. Add Pydantic contracts to `src/aae/contracts/` if cross-system types are needed.
3. Register the subsystem in `src/aae/controller/agent_registry.py`.
4. Write tests in `tests/unit/test_<subsystem>.py`.

## Bundled Sub-Projects

The repo bundles three upstream systems as read-only sub-projects:

| Directory | System | Role |
|---|---|---|
| `af-deep-research-main/` | Deep Research | Research orchestration |
| `sec-af-main/` | Sec-AF | Security analysis |
| `SWE-AF-main/` | SWE-AF | Software engineering automation |

AAE integrates with them through the adapter layer (`src/aae/adapters/`). Do not
modify the sub-project sources directly — raise PRs in their upstream repos instead.

## Documentation

| File | Contents |
|---|---|
| `README.md` | Project overview and quick-start |
| `docs/DEVELOPMENT.md` | This file — architecture and dev workflow |
| `docs/deep_integration.md` | Deep-integration build (OpenViking / SimpleMem / AgentShield) |
| `docs/FULL_UPGRADE_PLAN.md` | Historical upgrade plan (all 17 milestones) |
| `docs/UPGRADE_SCAFFOLD.md` | Original repo skeleton reference |
