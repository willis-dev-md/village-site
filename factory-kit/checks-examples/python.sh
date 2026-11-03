#!/usr/bin/env bash
# Example: Python project. Copy to scripts/checks.d/10-python.sh
cd "$(dirname "$0")/../.." || exit 1
python3 -m compileall -q . && { command -v ruff >/dev/null && ruff check . ; true; } && python3 -m pytest -q
