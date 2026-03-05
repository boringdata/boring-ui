#!/usr/bin/env bash
set -euo pipefail

# Deploy boring-ui edge mode: control plane + data plane (sandbox).
#
# Usage:
#   bash deploy/modal/deploy_edge_mode.sh
#   bash deploy/modal/deploy_edge_mode.sh --skip-sandbox

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BORING_SANDBOX_REPO="${BORING_SANDBOX_REPO:-$(cd "${REPO_ROOT}/.." && pwd)/boring-sandbox}"

SKIP_SANDBOX=false
for arg in "$@"; do
    case "$arg" in
        --skip-sandbox) SKIP_SANDBOX=true ;;
        *) echo "Unknown arg: $arg" >&2; exit 1 ;;
    esac
done

echo "==> Deploying boring-ui edge control plane..."
modal deploy "${REPO_ROOT}/deploy/modal/modal_app_edge.py"

if [ "$SKIP_SANDBOX" = true ]; then
    echo "==> Skipping sandbox deployment (--skip-sandbox)"
else
    if [[ ! -f "${BORING_SANDBOX_REPO}/src/boring_sandbox/modal_app.py" ]]; then
        echo "WARNING: boring-sandbox not found at ${BORING_SANDBOX_REPO}" >&2
        echo "Set BORING_SANDBOX_REPO to deploy the sandbox data plane." >&2
        echo "Skipping sandbox deployment."
    else
        echo "==> Deploying boring-sandbox data plane..."
        (cd "${BORING_SANDBOX_REPO}" && modal deploy src/boring_sandbox/modal_app.py)
    fi
fi

echo "==> Edge mode deployment complete."
