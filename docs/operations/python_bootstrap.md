# Python bootstrap

The Python runtime has one supported bootstrap path:

```bash
bash scripts/bootstrap_python.sh
```

That script is the canonical environment entrypoint for local verification and CI.

## What it does

`bootstrap_python.sh` performs exactly these steps from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r aae-engine/requirements.txt
```

`aae-engine/pyproject.toml` remains available for packaging metadata, but
`aae-engine/requirements.txt` is the operative dependency truth for bootstrap.

## Verification

Run all repository-level Python verification through the single wrapper:

```bash
bash scripts/verify_repo_state.sh
```

That script expects `.venv` to exist and then runs:

- `python scripts/check_contracts.py`
- `python scripts/drift_detector.py`
- `python -m compileall aae-engine/src`
- `python -m pytest --collect-only -q aae-engine/tests`

## Invariants

- The live runtime planner namespace is `aae.planning`.
- Oracle result ingestion flows through `aae.oracle_bridge.contracts`,
  `aae.oracle_bridge.oracle_adapters`, and `aae.oracle_bridge.result_service`.
- Compatibility layers such as `aae.planner` and
  `aae.oracle_bridge.result_contracts` must not return to the live runtime.
