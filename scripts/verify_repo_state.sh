#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".venv/bin/activate" ]; then
  echo "Bootstrap missing. Run scripts/bootstrap_python.sh first." >&2
  exit 1
fi

source .venv/bin/activate
export PYTHONPATH="$ROOT_DIR/aae-engine/src${PYTHONPATH:+:$PYTHONPATH}"

python scripts/check_contracts.py
python scripts/drift_detector.py
python -m compileall aae-engine/src
python -m pytest --collect-only -q aae-engine/tests
