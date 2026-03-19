# Quick start

## Run the AAE bridge

```bash
bash scripts/bootstrap_python.sh
source .venv/bin/activate
export PYTHONPATH="$PWD/aae-engine/src"
python -m aae.dashboard_api.server --host 127.0.0.1 --port 8787
```

## Probe the bridge

```bash
curl -X POST http://127.0.0.1:8787/api/oracle/plan   -H 'Content-Type: application/json'   -d '{
    "goal_id": "demo-1",
    "objective": "Repair the failing tests in the planner",
    "repo_path": ".",
    "state_summary": "planner tests are red",
    "constraints": {"mode": "strict"},
    "max_candidates": 4
  }'
```

## Oracle-side usage

1. Start the AAE dashboard on `127.0.0.1:8787`.
2. Keep `configs/oracle_aae_bridge.json` in the workspace root, or export `ORACLE_AAE_BASE_URL`.
3. Run Oracle on macOS from the workspace root.
4. The agent loop will fetch AAE advice automatically for code tasks and reconcile it with Oracle's local planner before execution.
