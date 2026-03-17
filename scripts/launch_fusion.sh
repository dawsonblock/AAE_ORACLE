#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/aae-engine"
python -m pip install -e .
python -m aae.dashboard_api.server --host 127.0.0.1 --port 8787
