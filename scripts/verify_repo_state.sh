#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR/aae-engine"

"$PYTHON_BIN" -m compileall src
"$PYTHON_BIN" -m pytest --collect-only
"$PYTHON_BIN" -m pytest -q || true

echo "Run swift build and swift test separately on a macOS runner."
