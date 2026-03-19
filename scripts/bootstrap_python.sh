#!/usr/bin/env bash
set -euo pipefail

if [ -z "${PYTHON_BIN+x}" ]; then
  PYTHON_BIN="python3"
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  fi
fi

rm -rf .venv

if ! "${PYTHON_BIN}" -m venv .venv; then
  "${PYTHON_BIN}" -m pip install --user virtualenv
  "${PYTHON_BIN}" -m virtualenv .venv
fi
source .venv/bin/activate

pip install --upgrade pip
pip install -r aae-engine/requirements.txt
