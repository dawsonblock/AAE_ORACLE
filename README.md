# Oracle–AAE Fusion v1.0.0

This repository merges **Oracle-OS** and **AAE Engine** into a single workspace with a concrete bridge layer.

## What is actually merged

- `oracle-os/` remains the **runtime authority**.
- `aae-engine/` remains the **search, mutation, and evaluation engine**.
- New bridge code lets Oracle ask AAE for ranked candidate commands over HTTP.
- New docs, compose, config, and tests are included.

## Important constraint

Oracle-OS contains macOS-specific automation code and cannot be fully containerized inside this workspace. The fusion upgrade therefore integrates at the **service boundary**:

- Oracle runs on macOS.
- AAE runs as a local HTTP service.
- Oracle requests candidate plans from AAE.
- Oracle still owns verification, execution, events, and state commit.

## Added upgrade surface

### In `aae-engine/`
- `src/aae/oracle_bridge/contracts.py`
- `src/aae/oracle_bridge/service.py`
- `src/aae/dashboard_api/routers/oracle.py`
- dashboard router registration in `src/aae/dashboard_api/server.py`
- integration test `tests/integration/test_oracle_bridge.py`

### In `oracle-os/`
- `Sources/OracleOS/Integration/OracleAAEModels.swift`
- `Sources/OracleOS/Integration/OracleAAEBridgeConfig.swift`
- `Sources/OracleOS/Integration/OracleAAEBridgeClient.swift`
- `Sources/OracleOS/Integration/OracleAAEExperimentCoordinator.swift`
- `docs/AAE_BRIDGE.md`

## Quick start

### 1. Start AAE

```bash
cd aae-engine
python -m pip install -e .
python -m aae.dashboard_api.server --host 127.0.0.1 --port 8787
```

### 2. Point Oracle to the AAE bridge

Oracle now auto-loads `configs/oracle_aae_bridge.json` from the workspace root. You can also set `ORACLE_AAE_CONFIG` or `ORACLE_AAE_BASE_URL`.

### 3. Planner integration

The Oracle agent loop now calls the AAE bridge during code planning. AAE can override weak exploratory code steps, preserve stronger workflow or graph-backed plans, and inject a preferred target path into Oracle code skills when the remote plan names one.

## Contract summary

**AAE endpoint**: `POST /api/oracle/plan`

Request fields:
- `goal_id`
- `objective`
- `repo_path`
- `state_summary`
- `constraints`
- `max_candidates`

Response fields:
- `goal_id`
- `engine`
- `summary`
- `warnings`
- `candidates[]`

Each candidate includes:
- `candidate_id`
- `kind`
- `tool`
- `payload`
- `rationale`
- `confidence`
- `predicted_score`
- `safety_class`

## Validation done here

- The new Python bridge code compiles.
- The new Python integration test passes.
- The merged workspace is zipped as a single distributable artifact.

Oracle source was not fully rebuilt in this environment because the runtime depends on macOS-only frameworks.
