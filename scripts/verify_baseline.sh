#!/usr/bin/env bash
set -e

echo "=== AAE Oracle Baseline Verification ==="

echo ""
echo "1. Running AAE tests..."
cd "$(dirname "$0")/../aae-engine"
python -m pytest tests/integration/test_oracle_bridge.py -q
echo "   ✓ Tests passed"

echo ""
echo "2. Starting AAE service..."
python -m aae.dashboard_api.server --host 127.0.0.1 --port 8787 &
PID=$!

# Give service time to start
sleep 3

echo "3. Checking endpoints..."
curl -sf http://127.0.0.1:8787/api/oracle/health || { echo "   ✗ /api/oracle/health failed"; kill $PID 2>/dev/null; exit 1; }
echo ""
echo "   ✓ /api/oracle/health OK"

curl -sf http://127.0.0.1:8787/api/oracle/fusion-stats || { echo "   ✗ /api/oracle/fusion-stats failed"; kill $PID 2>/dev/null; exit 1; }
echo ""
echo "   ✓ /api/oracle/fusion-stats OK"

kill $PID 2>/dev/null
wait $PID 2>/dev/null || true

echo ""
echo "=== Baseline OK ==="
