#!/usr/bin/env bash
set -euo pipefail

# Deploy boring-sandbox gateway via Modal (standalone sandbox deploy).
#
# Usage:
#   bash deploy/modal/deploy_sandbox_mode.sh
#
# Uses boring-sandbox source from vendor/boring-sandbox/ (git submodule).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Ensure submodule is initialized.
if [[ ! -f "${REPO_ROOT}/vendor/boring-sandbox/src/boring_sandbox/gateway/app.py" ]]; then
    echo "==> Initializing boring-sandbox submodule..."
    git -C "${REPO_ROOT}" submodule update --init vendor/boring-sandbox
fi

echo "==> Deploying boring-sandbox gateway..."
modal deploy "${REPO_ROOT}/deploy/modal/modal_app_sandbox.py"

echo "==> Sandbox deployment complete."
