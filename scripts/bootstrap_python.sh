#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"${PYTHON_BIN}" -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r aae-engine/requirements.txt
