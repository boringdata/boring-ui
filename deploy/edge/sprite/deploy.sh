#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SPRITE_NAME="${1:-${SPRITE_NAME:-}}"

if [[ -z "${SPRITE_NAME}" ]]; then
  echo "Usage: $0 <sprite-name>"
  echo "Or set SPRITE_NAME environment variable."
  exit 1
fi

if ! command -v sprite >/dev/null 2>&1; then
  echo "Error: sprite CLI not found."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm not found."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found."
  exit 1
fi

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "Warning: uvicorn not found locally; continuing (it is used in sprite runtime)."
fi

echo "[1/7] Building frontend artifact"
cd "${ROOT_DIR}"
npm ci
npm run build

echo "[2/7] Building backend wheel"
python3 -m pip wheel . -w /tmp/boring-ui-dist >/dev/null
WHEEL_PATH="$(ls -t /tmp/boring-ui-dist/boring_ui-*.whl | head -n1)"
if [[ -z "${WHEEL_PATH}" ]]; then
  echo "Error: backend wheel was not created."
  exit 1
fi

DEPLOY_TARBALL="/tmp/boring-ui-sprite-deploy.tgz"
WORK_DIR="/tmp/boring-ui-sprite-deploy"
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}/dist"

cp -R "${ROOT_DIR}/dist/." "${WORK_DIR}/dist/"
cp "${ROOT_DIR}/pyproject.toml" "${WORK_DIR}/"
cp "${ROOT_DIR}/README.md" "${WORK_DIR}/"
cp -R "${ROOT_DIR}/src/back" "${WORK_DIR}/src"
cp "${WHEEL_PATH}" "${WORK_DIR}/"

tar -C "${WORK_DIR}" -czf "${DEPLOY_TARBALL}" .

echo "[3/7] Ensuring sprite exists: ${SPRITE_NAME}"
sprite create "${SPRITE_NAME}" >/dev/null 2>&1 || true

echo "[4/7] Uploading artifact bundle"
sprite exec -s "${SPRITE_NAME}" \
  -file "${DEPLOY_TARBALL}:/home/sprite/boring-ui-sprite-deploy.tgz" \
  bash -lc 'rm -rf /home/sprite/boring-ui && mkdir -p /home/sprite/boring-ui && tar -xzf /home/sprite/boring-ui-sprite-deploy.tgz -C /home/sprite/boring-ui'

echo "[5/7] Installing app wheel in sprite"
sprite exec -s "${SPRITE_NAME}" -dir /home/sprite/boring-ui bash -lc '
  python3 -m pip install --upgrade pip >/dev/null
  python3 -m pip install --force-reinstall ./boring_ui-*.whl
'

echo "[6/7] Creating/updating service 'app' on port 8000"
sprite exec -s "${SPRITE_NAME}" bash -lc '
  set -euo pipefail
  if sprite-env services get app >/dev/null 2>&1; then
    sprite-env services delete app >/dev/null
  fi
  sprite-env services create app \
    --cmd bash \
    --args "-lc,cd /home/sprite/boring-ui && PYTHONPATH=/home/sprite/boring-ui/src/back BORING_UI_STATIC_DIR=/home/sprite/boring-ui/dist python3 -m uvicorn boring_ui.runtime:app --host 0.0.0.0 --port 8000" \
    --http-port 8000 \
    --no-stream
  sprite-env services start app >/dev/null || true
  sprite-env services get app
'

echo "[7/7] Deployment complete"
echo "Sprite URL:"
sprite -s "${SPRITE_NAME}" url
