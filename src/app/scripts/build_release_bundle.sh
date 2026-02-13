#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Build a release bundle for workspace provisioning.

This script produces the provisioning artifacts under an output directory
(default: ./dist):
  - bundle.tar.gz
  - bundle.tar.gz.sha256
  - manifest.json

The bundle.tar.gz contains:
  - dist/ (frontend build output)
  - boring_ui-*.whl (backend wheel)
  - deploy/sprite/bootstrap.sh
  - deploy/sprite/runtime.env.example

Usage:
  bash src/app/scripts/build_release_bundle.sh --release-id <id> [--app-id <id>] [--out-dir <dir>] [--skip-frontend]

Options:
  --release-id <id>   Release identifier (default: git-sha or timestamp)
  --app-id <id>       App identifier for manifest (default: boring-ui)
  --out-dir <dir>     Output directory for artifacts (default: dist)
  --skip-frontend     Skip frontend build step (expects dist/ already present)
  -h, --help          Show this help
EOF
}

RELEASE_ID=""
APP_ID="boring-ui"
OUT_DIR="dist"
SKIP_FRONTEND="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release-id)
      RELEASE_ID="${2:-}"
      shift 2
      ;;
    --app-id)
      APP_ID="${2:-}"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    --skip-frontend)
      SKIP_FRONTEND="true"
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$RELEASE_ID" ]]; then
  if git rev-parse --short HEAD >/dev/null 2>&1; then
    RELEASE_ID="$(git rev-parse --short HEAD)"
  else
    RELEASE_ID="$(date +%Y%m%d%H%M%S)"
  fi
fi

if [[ -z "$APP_ID" ]]; then
  echo "--app-id cannot be empty" >&2
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$REPO_ROOT" ]]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
fi

# Allow tests/CI to override where frontend dist comes from, without adding more flags.
FRONTEND_DIST_DIR="${FRONTEND_DIST_DIR:-${REPO_ROOT}/dist}"
SPRITE_DEPLOY_DIR="${SPRITE_DEPLOY_DIR:-${REPO_ROOT}/src/app/deploy/sprite}"

if [[ "${OUT_DIR}" = /* ]]; then
  OUT_ABS="${OUT_DIR}"
else
  OUT_ABS="${REPO_ROOT}/${OUT_DIR}"
fi
BUNDLE_PATH="${OUT_ABS}/bundle.tar.gz"
SHA_PATH="${OUT_ABS}/bundle.tar.gz.sha256"
MANIFEST_PATH="${OUT_ABS}/manifest.json"

TMP_ROOT="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_ROOT}"
}
trap cleanup EXIT

STAGING_DIR="${TMP_ROOT}/staging"
WHEEL_DIR="${TMP_ROOT}/wheels"

mkdir -p "${OUT_ABS}" "${STAGING_DIR}" "${WHEEL_DIR}"

echo "==> app_id:     ${APP_ID}"
echo "==> release_id: ${RELEASE_ID}"
echo "==> out_dir:    ${OUT_ABS}"

if [[ "${SKIP_FRONTEND}" != "true" ]]; then
  echo "==> Building frontend (npm run build)"
  (cd "${REPO_ROOT}" && npm run build)
fi

if [[ ! -d "${FRONTEND_DIST_DIR}" ]]; then
  echo "Missing frontend dist/ directory at ${FRONTEND_DIST_DIR}" >&2
  exit 1
fi

if [[ ! -f "${SPRITE_DEPLOY_DIR}/bootstrap.sh" ]]; then
  echo "Missing Sprite bootstrap script at ${SPRITE_DEPLOY_DIR}/bootstrap.sh" >&2
  exit 1
fi
if [[ ! -f "${SPRITE_DEPLOY_DIR}/runtime.env.example" ]]; then
  echo "Missing runtime env template at ${SPRITE_DEPLOY_DIR}/runtime.env.example" >&2
  exit 1
fi

echo "==> Building backend wheel"
(cd "${REPO_ROOT}" && python3 -m pip wheel --no-deps --wheel-dir "${WHEEL_DIR}" . >/dev/null)

WHEEL_PATH="$(
  find "${WHEEL_DIR}" -maxdepth 1 -type f -name "boring_ui-*.whl" -print -quit 2>/dev/null || true
)"
if [[ -z "${WHEEL_PATH}" ]]; then
  echo "Could not find backend wheel in ${WHEEL_DIR}" >&2
  exit 1
fi

echo "==> Staging bundle contents"
mkdir -p "${STAGING_DIR}/dist" "${STAGING_DIR}/deploy/sprite"

# Copy frontend output into staging/dist. Avoid accidentally re-bundling prior artifacts.
cp -R "${FRONTEND_DIST_DIR}/." "${STAGING_DIR}/dist/"
rm -f \
  "${STAGING_DIR}/dist/bundle.tar.gz" \
  "${STAGING_DIR}/dist/bundle.tar.gz.sha256" \
  "${STAGING_DIR}/dist/manifest.json" \
  "${STAGING_DIR}/dist/"boring_ui-*.whl 2>/dev/null || true

cp "${WHEEL_PATH}" "${STAGING_DIR}/"
cp "${SPRITE_DEPLOY_DIR}/bootstrap.sh" "${STAGING_DIR}/deploy/sprite/bootstrap.sh"
cp "${SPRITE_DEPLOY_DIR}/runtime.env.example" "${STAGING_DIR}/deploy/sprite/runtime.env.example"
chmod +x "${STAGING_DIR}/deploy/sprite/bootstrap.sh"

echo "==> Creating tarball"
tar -C "${STAGING_DIR}" -czf "${BUNDLE_PATH}" .

echo "==> Writing checksum"
BUNDLE_SHA="$(sha256sum "${BUNDLE_PATH}" | awk '{print $1}')"
if [[ "${OUT_DIR}" = /* ]]; then
  echo "${BUNDLE_SHA}  ${OUT_ABS}/bundle.tar.gz" > "${SHA_PATH}"
else
  echo "${BUNDLE_SHA}  ${OUT_DIR}/bundle.tar.gz" > "${SHA_PATH}"
fi

echo "==> Writing manifest"
CREATED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
GIT_SHA="$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || echo "unknown")"
WHEEL_FILE="$(basename "${WHEEL_PATH}")"

cat > "${MANIFEST_PATH}" <<EOF
{
  "app_id": "${APP_ID}",
  "release_id": "${RELEASE_ID}",
  "bundle_sha256": "${BUNDLE_SHA}",
  "created_at": "${CREATED_AT}",
  "git_sha": "${GIT_SHA}",
  "files": [
    "bundle.tar.gz",
    "bundle.tar.gz.sha256",
    "manifest.json"
  ],
  "bundle_contents": [
    "dist/",
    "${WHEEL_FILE}",
    "deploy/sprite/bootstrap.sh",
    "deploy/sprite/runtime.env.example"
  ]
}
EOF

echo "==> Done"
echo "bundle:    ${BUNDLE_PATH}"
echo "checksum:  ${SHA_PATH}"
echo "manifest:  ${MANIFEST_PATH}"
