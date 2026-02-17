#!/usr/bin/env bash
# Validate E2E example app environment before scenario execution.
# Bead: bd-223o.16.2 (K2)
#
# Checks:
#   1. Sprite is running and /health returns 200.
#   2. /metrics endpoint is exposed.
#   3. /api/capabilities returns expected features.
#   4. Seed manifest exists with expected user/workspace data.
#   5. X-Request-ID correlation header is echoed.
#
# Usage:
#   bash deploy/example-app/validate.sh
#   bash deploy/example-app/validate.sh <base-url>
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
DEPLOY_DIR="${ROOT_DIR}/deploy/example-app"

# Load config if present.
if [[ -f "${DEPLOY_DIR}/config.env" ]]; then
  # shellcheck disable=SC1091
  source "${DEPLOY_DIR}/config.env"
fi

SPRITE_NAME="${SPRITE_NAME:-boring-ui-e2e}"

# Accept explicit base URL or derive from sprite.
if [[ -n "${1:-}" ]]; then
  BASE_URL="$1"
elif command -v sprite >/dev/null 2>&1; then
  BASE_URL="$(sprite -s "${SPRITE_NAME}" url 2>/dev/null | head -1 || echo "")"
  BASE_URL="${BASE_URL%/}"
fi

if [[ -z "${BASE_URL:-}" ]]; then
  echo "Error: No base URL. Pass as argument or ensure sprite CLI is available."
  exit 1
fi

PASS=0
FAIL=0

check() {
  local name="$1"
  shift
  if "$@"; then
    echo "  PASS: ${name}"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: ${name}"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== E2E Environment Validation ==="
echo "URL: ${BASE_URL}"
echo ""

# ── 1. Health check ──────────────────────────────────────────────────

echo "[1/5] Health check"
check "/health returns 200" \
  curl -sf -o /dev/null -w '' "${BASE_URL}/health"

# ── 2. Metrics endpoint ──────────────────────────────────────────────

echo "[2/5] Metrics endpoint"
check "/metrics returns prometheus data" \
  bash -c "curl -sf '${BASE_URL}/metrics' | grep -q 'http_server_requests_total'"

# ── 3. Capabilities ─────────────────────────────────────────────────

echo "[3/5] Capabilities"
check "/api/capabilities returns features" \
  bash -c "curl -sf '${BASE_URL}/api/capabilities' | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d.get(\"features\",{}).get(\"files\") is True'"

# ── 4. Seed manifest ────────────────────────────────────────────────

echo "[4/5] Seed manifest"
MANIFEST="${DEPLOY_DIR}/seed_manifest.json"
check "seed_manifest.json exists" \
  test -f "${MANIFEST}"
if [[ -f "${MANIFEST}" ]]; then
  check "manifest has workspace entries" \
    bash -c "python3 -c 'import json; d=json.load(open(\"${MANIFEST}\")); assert len(d) >= 2'"
fi

# ── 5. Request-ID correlation ────────────────────────────────────────

echo "[5/5] Request-ID correlation"
check "X-Request-ID echoed on response" \
  bash -c "curl -sf -D - -o /dev/null '${BASE_URL}/health' -H 'X-Request-ID: validate-check-001' 2>&1 | grep -qi 'x-request-id: validate-check-001'"

# ── Summary ──────────────────────────────────────────────────────────

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [[ ${FAIL} -gt 0 ]]; then
  echo "Environment NOT ready for scenario execution."
  exit 1
else
  echo "Environment ready for scenario execution."
  exit 0
fi
