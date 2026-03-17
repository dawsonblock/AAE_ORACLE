# Oracle–AAE Fusion

> A unified autonomous software engineering system that merges **Oracle OS** (macOS Swift runtime) with the **AAE Engine** (Python AI engineering platform) through a strict, structured service boundary.

[![Version](https://img.shields.io/badge/version-1.0.0-blue?style=for-the-badge)](#)
[![Oracle OS](https://img.shields.io/badge/Oracle%20OS-Swift%20%2F%20macOS-orange?style=for-the-badge&logo=swift)](#oracle-os)
[![AAE Engine](https://img.shields.io/badge/AAE%20Engine-Python%203.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](#aae-engine)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](#license)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Authority Split](#authority-split)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Contract](#api-contract)
- [Candidate Schema](#candidate-schema)
- [Integration Details](#integration-details)
- [Running Tests](#running-tests)
- [Docker](#docker)
- [Environment Variables](#environment-variables)
- [Development Notes](#development-notes)

---

## Overview

Oracle–AAE Fusion v1.0.0 integrates two previously separate systems:

| System | Language | Responsibility |
|--------|----------|----------------|
| **Oracle OS** | Swift (macOS) | Verified execution, state, events, recovery |
| **AAE Engine** | Python 3.11+ | Candidate search, localization, scoring, patch generation |

The two systems communicate over a local HTTP boundary — AAE **proposes**, Oracle **executes**. Neither system has authority over the other’s domain.

> **Important:** Oracle OS uses macOS-only Accessibility and runtime frameworks and cannot run inside a container. The integration lives at the service boundary, not inside a shared process.

---

## Architecture

```
User Goal / Intent
       │
       ▼
 Oracle Planner
       │
       ├────────────────────────────────────────────┐
       │                                              │
       ▼                                              ▼
Oracle Local Plan                         AAE Bridge Request
(workflow / graph strategy)               POST /api/oracle/plan
                                                     │
                                                     ▼
                                 AAE Candidate Generation & Ranking
                                 (repo profiling, localization,
                                  patch hints, predicted scores)
                                                     │
       ┌─────────────────────────────────────────────┘
       │
       ▼
  Plan Reconciliation
  (stronger Oracle plan preserved;
   AAE overrides weak exploratory steps)
       │
       ▼
 Oracle Verification
       │
       ▼
 Oracle Verified Execution
       │
       ▼
 Oracle Domain Events
       │
       ▼
 Oracle Commit Coordinator
       │
       ▼
 Committed World State + Traces
```

---

## Authority Split

This split is intentional and enforced. Do not collapse it.

| Concern | Owner |
|---------|-------|
| Host-side side effects | **Oracle OS** |
| Action verification | **Oracle OS** |
| Event emission | **Oracle OS** |
| State commit | **Oracle OS** |
| Recovery & retry | **Oracle OS** |
| Candidate search | **AAE Engine** |
| Repository localization | **AAE Engine** |
| Patch generation hints | **AAE Engine** |
| Scoring & ranking | **AAE Engine** |
| Experiment simulation | **AAE Engine** |

AAE may **never** return raw shell commands or directly executable host-side strings. It returns structured candidates only.

---

## Repository Structure

```
oracle-aae-fusion-v1.0.0/
├── oracle-os/                          # Swift macOS runtime (Oracle OS)
│   ├── Sources/OracleOS/
│   │   ├── Integration/                # Bridge client, config, models (NEW)
│   │   │   ├── OracleAAEBridgeClient.swift
│   │   │   ├── OracleAAEBridgeConfig.swift
│   │   │   ├── OracleAAECandidateValidator.swift
│   │   │   ├── OracleAAEExperimentCoordinator.swift
│   │   │   ├── OracleAAEModels.swift
│   │   │   └── OracleAAEPlanningAdvisor.swift
│   │   ├── Execution/                  # Verified execution kernel
│   │   ├── Planning/                   # Planner, strategies, graph search
│   │   ├── Runtime/                    # Orchestrator, coordinators, lifecycle
│   │   ├── WorldModel/                 # Perception, AX scanning, state
│   │   ├── Learning/                   # Trace, memory, recipes, workflows
│   │   ├── Recovery/                   # Failure classification, strategies
│   │   └── MCP/                        # MCP server & tool dispatcher
│   ├── Tests/                          # Swift tests (evals + unit)
│   ├── ARCHITECTURE.md
│   ├── ARCHITECTURE_RULES.md
│   └── docs/
│       └── AAE_BRIDGE.md               # Oracle-side bridge documentation
│
├── aae-engine/                         # Python AI engineering platform (AAE)
│   ├── src/aae/
│   │   ├── oracle_bridge/              # Bridge contracts & service (NEW)
│   │   │   ├── contracts.py            # Pydantic request/response schemas
│   │   │   └── service.py              # OraclePlanningBridge implementation
│   │   ├── dashboard_api/
│   │   │   ├── routers/oracle.py       # POST /api/oracle/plan endpoint (NEW)
│   │   │   └── server.py               # FastAPI app (bridge router registered)
│   │   ├── localization/               # Multi-signal fault localization
│   │   ├── planner/                    # Strategic planning & LLM consensus
│   │   ├── patching/                   # Patch application & iterative repair
│   │   ├── sandbox/                    # Docker-based isolated execution
│   │   ├── evaluation/                 # Scoring, benchmarks, metrics
│   │   ├── graph/                      # Symbol & dependency graph analysis
│   │   └── learning/                   # Experiment history & feedback
│   ├── tests/
│   │   └── integration/
│   │       └── test_oracle_bridge.py   # Bridge integration tests (NEW)
│   ├── pyproject.toml
│   └── requirements.txt
│
├── configs/
│   └── oracle_aae_bridge.json          # Bridge runtime configuration
│
├── docs/
│   ├── merged_architecture.md          # Full architecture description
│   ├── integration_contract.md         # HTTP contract with examples
│   ├── candidate_schema.md             # Strict candidate schema & validation
│   ├── quickstart.md                   # Step-by-step startup guide
│   └── oracle_aae_fusion_plan.md       # Full integration build plan
│
├── docker-compose.yml                  # Starts AAE dashboard service
├── fusion_manifest.json                # Manifest of all added/modified files
└── scripts/
    └── launch_fusion.sh                # Convenience launch script
```

---

## Quick Start

### Prerequisites

- macOS (required for Oracle OS)
- Python 3.11+
- Swift 5.9+ / Xcode (for Oracle OS)
- Docker (optional, for AAE containerized mode)

### 1. Install and start AAE

```bash
cd aae-engine
python -m pip install -e .
python -m aae.dashboard_api.server --host 127.0.0.1 --port 8787
```

The AAE bridge endpoint will be live at `http://127.0.0.1:8787/api/oracle/plan`.

### 2. Probe the bridge

```bash
curl -X POST http://127.0.0.1:8787/api/oracle/plan \\
  -H 'Content-Type: application/json' \\
  -d '{
    "goal_id": "demo-1",
    "objective": "Repair the failing tests in the planner",
    "repo_path": ".",
    "state_summary": "planner tests are red",
    "constraints": {"mode": "strict"},
    "max_candidates": 4
  }'
```

### 3. Run Oracle on macOS

Oracle auto-loads the bridge config from `configs/oracle_aae_bridge.json`. Run Oracle from the workspace root:

```bash
# From the workspace root
swift run oracle
```

Oracle will automatically consult AAE for code tasks and reconcile AAE advice with its local planner before executing.

---

## Configuration

### `configs/oracle_aae_bridge.json`

```json
{
  "base_url": "http://127.0.0.1:8787",
  "plan_endpoint": "/api/oracle/plan",
  "result_endpoint": "/api/oracle/experiment_result",
  "timeout_seconds": 30,
  "max_candidates_per_goal": 5,
  "max_execution_attempts": 3,
  "max_patch_files": 3,
  "max_total_runtime_seconds": 300,
  "max_failed_attempts_before_abort": 2,
  "enabled": true
}
```

Oracle loads config in this priority order:

1. `ORACLE_AAE_CONFIG` env var (path to a custom JSON file)
2. `./configs/oracle_aae_bridge.json` (workspace root default)
3. Individual environment variables (see [Environment Variables](#environment-variables))

---

## API Contract

### `POST /api/oracle/plan`

#### Request

```json
{
  "goal_id": "repair-123",
  "objective": "Repair the failing login flow and validate the patch",
  "repo_path": "/repos/app",
  "state_summary": "2 failing tests in auth/login",
  "constraints": {
    "approval_mode": "strict",
    "max_patch_files": 3
  },
  "max_candidates": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `goal_id` | string | ✅ | Unique goal identifier |
| `objective` | string | ✅ | Human-readable goal description |
| `repo_path` | string | ✅ | Absolute path to the repository |
| `state_summary` | string | ✅ | Current failure/state description |
| `constraints` | object | ❌ | Optional execution constraints |
| `max_candidates` | int | ❌ | Max candidates to return (default: 5) |

#### Response

```json
{
  "goal_id": "repair-123",
  "engine": "aae.oracle_bridge.v1",
  "summary": {
    "repo_profile": {
      "dominant_language": "python",
      "file_count": 114
    },
    "recommended_test_command": "pytest -q"
  },
  "warnings": [],
  "candidates": [
    {
      "candidate_id": "repair-123-inspect",
      "kind": "aae.inspect_repository",
      "tool": "repository_analyzer",
      "payload": { "repo_path": "/repos/app" },
      "rationale": "Build a grounded repository and language profile before mutating code.",
      "confidence": 0.94,
      "predicted_score": 0.68,
      "safety_class": "read_only"
    }
  ]
}
```

---

## Candidate Schema

AAE returns structured candidates only. Every candidate is validated by Oracle’s `OracleAAECandidateValidator` before entering the planning pipeline. See [docs/candidate_schema.md](docs/candidate_schema.md) for the full spec.

### Allowed `kind` values

| Kind | Description |
|------|-------------|
| `aae.inspect_repository` | Profile the repository before mutation |
| `aae.analyze_objective` | Rank next-step analysis without strong repo signal |
| `aae.run_targeted_tests` | Reproduce failure surface, capture baseline |
| `aae.localize_failure` | Fuse failure symptoms into a smaller edit region |
| `aae.generate_patch` | Generate a bounded candidate patch |
| `aae.validate_candidate` | Run candidate through the test command |
| `aae.estimate_change_impact` | Estimate dependency blast radius |

### Allowed `safety_class` values

| Class | Requires Approval |
|-------|------------------|
| `read_only` | No |
| `bounded_mutation` | No |
| `sandboxed_write` | No |
| `requires_approval` | **Yes** |

Candidates with unknown `kind` values, unknown tool names, or missing required fields are **rejected** before they reach Oracle’s planner.

---

## Integration Details

### Added to `aae-engine/`

| File | Purpose |
|------|---------|
| `src/aae/oracle_bridge/contracts.py` | Pydantic schemas for `OraclePlanRequest`, `OraclePlanResponse`, `OracleCandidateCommand` |
| `src/aae/oracle_bridge/service.py` | `OraclePlanningBridge` — assembles and ranks candidates |
| `src/aae/dashboard_api/routers/oracle.py` | FastAPI router exposing `POST /api/oracle/plan` |
| `tests/integration/test_oracle_bridge.py` | Integration tests for the bridge endpoint |

### Added to `oracle-os/`

| File | Purpose |
|------|---------|
| `Sources/OracleOS/Integration/OracleAAEModels.swift` | Swift Codable models mirroring the bridge contract |
| `Sources/OracleOS/Integration/OracleAAEBridgeConfig.swift` | Bridge configuration loader |
| `Sources/OracleOS/Integration/OracleAAEBridgeClient.swift` | Async HTTP client to call AAE |
| `Sources/OracleOS/Integration/OracleAAECandidateValidator.swift` | Validates and filters incoming candidates |
| `Sources/OracleOS/Integration/OracleAAEExperimentCoordinator.swift` | Feeds AAE experiment results back to the planner |
| `Sources/OracleOS/Integration/OracleAAEPlanningAdvisor.swift` | Reconciles Oracle and AAE plans |

### Planner Reconciliation Rules

1. Oracle evaluates its own local plan (workflow/graph-backed strategy score).
2. Oracle fetches AAE candidates for code tasks.
3. If Oracle’s plan is **strong** (high workflow or graph confidence), it is preserved.
4. If Oracle’s plan is **weak** (exploratory), AAE candidates may override it.
5. When AAE names a preferred target file, Oracle code skills pick it up automatically.

---

## Running Tests

### AAE bridge integration tests

```bash
cd aae-engine
pip install -e ".[dev]"
pytest tests/integration/test_oracle_bridge.py -v
```

### Oracle OS tests (macOS only)

```bash
cd oracle-os
swift test
```

### Full AAE test suite

```bash
cd aae-engine
pytest tests/ -v
```

---

## Docker

The AAE dashboard can be run in Docker. Oracle OS must run natively on macOS.

```bash
# From the workspace root
docker compose up
```

The AAE bridge will be available on `http://localhost:8787`.

> **Note:** Oracle OS is not included in the Docker service. It must be run natively on macOS alongside the container.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORACLE_AAE_CONFIG` | — | Path to a custom bridge config JSON file |
| `ORACLE_AAE_BASE_URL` | `http://127.0.0.1:8787` | AAE service base URL |
| `ORACLE_AAE_ENABLED` | `true` | Enable/disable the bridge at runtime |
| `ORACLE_AAE_PLAN_ENDPOINT` | `/api/oracle/plan` | Override the plan endpoint path |
| `ORACLE_AAE_TIMEOUT_SECONDS` | `30` | HTTP request timeout |
| `ORACLE_AAE_MAX_CANDIDATES` | `5` | Max candidates to request per goal |
| `ORACLE_AAE_MIN_OVERRIDE_SCORE` | — | Minimum AAE score required to override Oracle’s plan |

---

## Development Notes

- **Oracle OS** is macOS-only. It depends on `Accessibility`, `AppKit`, and Swift concurrency. It cannot be containerized.
- **AAE Engine** is Python 3.11+ and platform-agnostic. It can run in Docker or natively.
- The bridge contract is versioned (`aae.candidate.v1`). Changes to the schema must be reflected in both `contracts.py` and `OracleAAEModels.swift`.
- Oracle’s `OracleAAECandidateValidator` is the enforcement point — all incoming candidates are filtered there before they reach the planner.
- AAE **must never** return raw shell commands or host-executable strings. See [docs/candidate_schema.md](docs/candidate_schema.md) for the full validation ruleset.

---

## License

MIT — see individual component licenses in `aae-engine/LICENSE` and `oracle-os/Vendor/AXorcist/LICENSE`.
