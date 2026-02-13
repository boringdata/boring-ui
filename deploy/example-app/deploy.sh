#!/usr/bin/env bash
# Deploy boring-ui example app for E2E scenario validation.
# Bead: bd-223o.16.2 (K2)
#
# Usage:
#   bash deploy/example-app/deploy.sh
#   bash deploy/example-app/deploy.sh <sprite-name>
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deploy/example-app"

# Load config if present.
if [[ -f "${DEPLOY_DIR}/config.env" ]]; then
  # shellcheck disable=SC1091
  source "${DEPLOY_DIR}/config.env"
fi

SPRITE_NAME="${1:-${SPRITE_NAME:-boring-ui-e2e}}"
RELEASE_ID="e2e-v0-$(git -C "${ROOT_DIR}" rev-parse --short HEAD)"

echo "=== Boring UI E2E Deployment ==="
echo "Sprite:     ${SPRITE_NAME}"
echo "Release ID: ${RELEASE_ID}"
echo "App ID:     ${APP_ID:-e2e-example}"
echo ""

# ── Pre-flight checks ────────────────────────────────────────────────

for cmd in sprite npm python3; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Error: ${cmd} not found in PATH."
    exit 1
  fi
done

# ── Build artifacts ──────────────────────────────────────────────────

echo "[1/6] Building frontend"
cd "${ROOT_DIR}"
npm ci --silent
npm run build

echo "[2/6] Building backend wheel"
python3 -m pip wheel . -w /tmp/boring-ui-e2e-dist >/dev/null 2>&1
WHEEL_PATH="$(ls -t /tmp/boring-ui-e2e-dist/boring_ui-*.whl | head -n1)"

# Bundle deployment artifacts.
WORK_DIR="/tmp/boring-ui-e2e-deploy"
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}/dist" "${WORK_DIR}/config"

cp -R "${ROOT_DIR}/dist/." "${WORK_DIR}/dist/"
cp -R "${ROOT_DIR}/src/back" "${WORK_DIR}/src"
cp "${ROOT_DIR}/pyproject.toml" "${WORK_DIR}/"
cp "${WHEEL_PATH}" "${WORK_DIR}/"
cp "${DEPLOY_DIR}/app_identity.json" "${WORK_DIR}/config/"

TARBALL="/tmp/boring-ui-e2e-deploy.tgz"
tar -C "${WORK_DIR}" -czf "${TARBALL}" .

# ── Deploy to sprite ────────────────────────────────────────────────

echo "[3/6] Ensuring sprite: ${SPRITE_NAME}"
sprite create "${SPRITE_NAME}" >/dev/null 2>&1 || true

echo "[4/6] Uploading artifact bundle"
sprite exec -s "${SPRITE_NAME}" \
  -file "${TARBALL}:/home/sprite/boring-ui-e2e.tgz" \
  bash -lc '
    rm -rf /home/sprite/boring-ui
    mkdir -p /home/sprite/boring-ui
    tar -xzf /home/sprite/boring-ui-e2e.tgz -C /home/sprite/boring-ui
  '

echo "[5/6] Installing in sprite"
sprite exec -s "${SPRITE_NAME}" -dir /home/sprite/boring-ui bash -lc '
  python3 -m pip install --upgrade pip >/dev/null
  python3 -m pip install --force-reinstall ./boring_ui-*.whl
'

echo "[6/6] Creating service on port ${CONTROL_PLANE_PORT:-8000}"
sprite exec -s "${SPRITE_NAME}" bash -lc "
  set -euo pipefail
  if sprite-env services get app >/dev/null 2>&1; then
    sprite-env services delete app >/dev/null
  fi
  sprite-env services create app \\
    --cmd bash \\
    --args '-lc,cd /home/sprite/boring-ui && PYTHONPATH=/home/sprite/boring-ui/src/back BORING_UI_STATIC_DIR=/home/sprite/boring-ui/dist LOG_FORMAT=${LOG_FORMAT:-json} LOG_LEVEL=${LOG_LEVEL:-INFO} python3 -m uvicorn boring_ui.runtime:app --host 0.0.0.0 --port ${CONTROL_PLANE_PORT:-8000}' \\
    --http-port ${CONTROL_PLANE_PORT:-8000} \\
    --no-stream
  sprite-env services start app >/dev/null || true
"

# ── Output ──────────────────────────────────────────────────────────

echo ""
echo "=== Deployment Complete ==="
echo "Sprite:     ${SPRITE_NAME}"
echo "Release ID: ${RELEASE_ID}"
echo "URL:"
sprite -s "${SPRITE_NAME}" url
echo ""
echo "Next steps:"
echo "  1. Set sprite to public: sprite -s ${SPRITE_NAME} url update --auth public"
echo "  2. Seed test data:       python3 deploy/example-app/seed.py"
echo "  3. Validate environment: bash deploy/example-app/validate.sh"
