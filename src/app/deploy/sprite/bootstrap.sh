#!/usr/bin/env bash
set -euo pipefail

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] $*"; }
die() { echo "[$(ts)] ERROR: $*" >&2; exit 1; }

SCRIPT_PATH="$(readlink -f "$0" 2>/dev/null || true)"
if [[ -z "${SCRIPT_PATH}" ]]; then
  # readlink -f is not guaranteed everywhere.
  SCRIPT_PATH="$0"
fi
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"

# If this script is run from inside an extracted bundle, it will typically live at:
#   <root>/deploy/sprite/bootstrap.sh
APP_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

PORT="${PORT:-8000}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-${APP_ROOT}/workspace}"
INSTALL_DIR="${INSTALL_DIR:-${APP_ROOT}/runtime}"

mkdir -p "${WORKSPACE_ROOT}" "${INSTALL_DIR}"

find_bundle() {
  if [[ -n "${BUNDLE_PATH:-}" && -f "${BUNDLE_PATH}" ]]; then
    echo "${BUNDLE_PATH}"
    return 0
  fi
  if [[ -f "${APP_ROOT}/bundle.tar.gz" ]]; then
    echo "${APP_ROOT}/bundle.tar.gz"
    return 0
  fi
  if [[ -f "bundle.tar.gz" ]]; then
    echo "bundle.tar.gz"
    return 0
  fi
  return 1
}

log "BOOTSTRAP start (app_root=${APP_ROOT})"
log "Using PORT=${PORT} WORKSPACE_ROOT=${WORKSPACE_ROOT} INSTALL_DIR=${INSTALL_DIR}"

BUNDLE_FILE="$(find_bundle || true)"
if [[ -z "${BUNDLE_FILE}" ]]; then
  die "bundle.tar.gz not found (set BUNDLE_PATH or place bundle.tar.gz in current dir or ${APP_ROOT})"
fi

log "Using bundle: ${BUNDLE_FILE}"

# Idempotent unpack: if we already unpacked this exact bundle sha, skip.
CURRENT_SHA="$(sha256sum "${BUNDLE_FILE}" | awk '{print $1}')"
SHA_MARKER="${INSTALL_DIR}/.bundle_sha256"
if [[ -f "${SHA_MARKER}" ]] && [[ "$(cat "${SHA_MARKER}")" == "${CURRENT_SHA}" ]] && [[ -d "${INSTALL_DIR}/dist" ]]; then
  log "Bundle already unpacked for sha=${CURRENT_SHA}; skipping unpack"
else
  log "Unpacking bundle into ${INSTALL_DIR}"
  rm -rf "${INSTALL_DIR}"
  mkdir -p "${INSTALL_DIR}"
  tar -C "${INSTALL_DIR}" -xzf "${BUNDLE_FILE}"
  echo "${CURRENT_SHA}" > "${SHA_MARKER}"
fi

WHEEL_PATH="$(
  find "${INSTALL_DIR}" -maxdepth 1 -type f -name "boring_ui-*.whl" -print -quit 2>/dev/null || true
)"
if [[ -z "${WHEEL_PATH}" ]]; then
  die "backend wheel not found after unpack (expected boring_ui-*.whl in ${INSTALL_DIR})"
fi

if [[ -f "${INSTALL_DIR}/runtime.env" ]]; then
  log "Sourcing runtime.env"
  # shellcheck disable=SC1091
  source "${INSTALL_DIR}/runtime.env"
else
  log "No runtime.env found; relying on injected environment"
fi

log "Installing backend wheel: ${WHEEL_PATH}"
python3 -m pip install --no-deps --force-reinstall "${WHEEL_PATH}" >/dev/null

log "Starting backend (uvicorn factory) on 127.0.0.1:${PORT}"
export WORKSPACE_ROOT

# Avoid starting multiple servers if re-run. We use a pidfile in INSTALL_DIR.
PIDFILE="${INSTALL_DIR}/runtime.pid"
if [[ -f "${PIDFILE}" ]]; then
  OLD_PID="$(cat "${PIDFILE}" || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    log "Runtime already running (pid=${OLD_PID}); skipping start"
  else
    rm -f "${PIDFILE}"
  fi
fi

if [[ ! -f "${PIDFILE}" ]]; then
  nohup python3 -m uvicorn boring_ui.api.app:create_app --factory --host 127.0.0.1 --port "${PORT}" \
    > "${INSTALL_DIR}/runtime.log" 2>&1 &
  echo "$!" > "${PIDFILE}"
  log "Runtime started (pid=$(cat "${PIDFILE}"))"
fi

log "Health check: GET /health"
for _ in {1..30}; do
  if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null; then
    log "Health check OK"
    log "BOOTSTRAP success"
    exit 0
  fi
  sleep 1
done

die "Health check failed after 30s; see ${INSTALL_DIR}/runtime.log"
