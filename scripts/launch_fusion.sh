#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
AAE_HOST="${AAE_HOST:-127.0.0.1}"
AAE_PORT="${AAE_PORT:-8000}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8787}"

AAE_PID=""
DASHBOARD_PID=""

cleanup() {
  local pids=()
  [[ -n "$AAE_PID" ]]       && pids+=("$AAE_PID")
  [[ -n "$DASHBOARD_PID" ]] && pids+=("$DASHBOARD_PID")
  if [[ ${#pids[@]} -gt 0 ]]; then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR/aae-engine"
"$PYTHON_BIN" -m pip install -e .

"$PYTHON_BIN" -m uvicorn aae.oracle_bridge.service:app --host "$AAE_HOST" --port "$AAE_PORT" > /tmp/aae-service.log 2>&1 &
AAE_PID=$!

for _ in $(seq 1 20); do
  if curl -fsS "http://$AAE_HOST:$AAE_PORT/health" >/dev/null; then
    break
  fi
  sleep 1
done

curl -fsS "http://$AAE_HOST:$AAE_PORT/health" >/dev/null

"$PYTHON_BIN" -m aae.dashboard_api.server --host "$AAE_HOST" --port "$DASHBOARD_PORT" > /tmp/aae-dashboard.log 2>&1 &
DASHBOARD_PID=$!

export ORACLE_AAE_ENDPOINT="http://$AAE_HOST:$AAE_PORT"

echo "AAE service running at $ORACLE_AAE_ENDPOINT (pid=$AAE_PID)"
echo "Dashboard running at http://$AAE_HOST:$DASHBOARD_PORT (pid=$DASHBOARD_PID)"
