#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$PROJECT/tools"
VENV="$PROJECT/.venv"
if [ ! -x "$VENV/bin/python" ]; then python3 -m venv "$VENV"; fi
PIP_CACHE_DIR="$TOOLS/pip-cache" "$VENV/bin/python" -m pip install -r "$TOOLS/capture-requirements.lock"
"$VENV/bin/python" -m pip check
cd "$PROJECT"
"$VENV/bin/python" checks/test_media_contract.py
