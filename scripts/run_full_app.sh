#!/usr/bin/env bash
set -euo pipefail

# Backward-compatible positional config support:
#   scripts/run_full_app.sh app.full.toml --deploy-mode sandbox-proxy
if [[ $# -gt 0 && "${1:-}" != -* ]]; then
  CONFIG="$1"
  shift
  set -- --config "$CONFIG" "$@"
fi

python3 scripts/run_full_app.py "$@"
