#!/usr/bin/env bash
set -euo pipefail
CONFIG=${1:-app.full.toml}
python3 scripts/run_full_app.py --config "$CONFIG"
