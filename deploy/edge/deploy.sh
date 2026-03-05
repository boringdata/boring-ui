#!/usr/bin/env bash
set -euo pipefail

# Deploy boring-ui edge mode: control plane + data plane (sandbox).
#
# The sandbox source lives at vendor/boring-sandbox/ (git submodule).
# Both Modal apps are defined in deploy/edge/.
#
# Usage:
#   bash deploy/edge/deploy.sh
#   bash deploy/edge/deploy.sh --skip-sandbox

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SKIP_SANDBOX=false
for arg in "$@"; do
    case "$arg" in
        --skip-sandbox) SKIP_SANDBOX=true ;;
        *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
done

# Ensure submodule is initialized.
VENDOR_SANDBOX="${REPO_ROOT}/vendor/boring-sandbox"
if [[ ! -d "${VENDOR_SANDBOX}/src/boring_sandbox" ]]; then
    echo "==> Initializing boring-sandbox submodule..."
    git -C "${REPO_ROOT}" submodule update --init vendor/boring-sandbox
fi

echo "==> Deploying boring-ui edge control plane..."
modal deploy "${REPO_ROOT}/deploy/edge/modal_app.py"

if [ "$SKIP_SANDBOX" = true ]; then
    echo "==> Skipping sandbox deployment (--skip-sandbox)"
else
    echo "==> Deploying boring-sandbox data plane..."
    modal deploy "${REPO_ROOT}/deploy/edge/modal_app_sandbox.py"
fi

echo "==> Edge mode deployment complete."
