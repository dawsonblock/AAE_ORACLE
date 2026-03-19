# Runtime Baseline

Measured on Linux (Cursor cloud agent) on 2026-03-19 after the runtime repair sequence.

## Python verification

Commands run from `aae-engine/`:

```bash
python3 -m compileall src
python3 -m pytest --collect-only
python3 -m pytest -q
```

Observed result:

```text
269 passed, 1 skipped
```

Collection is clean, and `compileall` completes without syntax errors across `src/`.

## Current supported runtime state

- Canonical execution adapter: `aae.execution.sandbox_adapter.SandboxAdapter`
- Canonical planning package: `aae.planning`
- Canonical repair loop: `aae.repair.repair_loop.RepairLoop`
- Persistent experiment store: `aae.storage.experiment_store.ExperimentStore`
- Persistent ranking store: `aae.storage.ranking_store.RankingStore`
- Replay by `trace_id`: `aae.analysis.replay.ReplayEngine.get_history`
- Bridge service entrypoint: `aae.oracle_bridge.service:app`
- Persistent observability log: `logs/events.jsonl`

## Dashboard surfaces

The checked-in dashboard HTML is intentionally limited to:

- recent experiments
- replay by trace ID
- score chart
- acceptance/rejection summary

## Swift validation status

This repair run was executed on Linux, and the host did not include a Swift toolchain (`swift: command not found`).

Because of that:

- Python runtime verification is complete
- macOS Swift verification remains pending on a macOS runner:
  - `swift build`
  - `swift test`
