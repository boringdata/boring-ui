#!/usr/bin/env bash
# smoke_check.sh - Health + compatibility + exec sanity checks
#
# Validates that the deployed workspace service is healthy, version-compatible,
# and responds correctly to basic requests.
#
# Required environment:
#   SPRITES_WORKSPACE_SERVICE_HOST  - Workspace service hostname
#   SPRITES_WORKSPACE_SERVICE_PORT  - Workspace service port
#
# Optional environment:
#   SPRITES_WORKSPACE_SERVICE_PATH  - Base path (default: /)
#   SMOKE_TIMEOUT                   - HTTP timeout in seconds (default: 5)
#   EXPECTED_VERSION                - Expected API version (default: 0.1.0)
#
set -euo pipefail

: "${SPRITES_WORKSPACE_SERVICE_HOST:?SPRITES_WORKSPACE_SERVICE_HOST is required}"
: "${SPRITES_WORKSPACE_SERVICE_PORT:?SPRITES_WORKSPACE_SERVICE_PORT is required}"

SERVICE_PATH="${SPRITES_WORKSPACE_SERVICE_PATH:-/}"
SMOKE_TIMEOUT="${SMOKE_TIMEOUT:-5}"
EXPECTED_VERSION="${EXPECTED_VERSION:-0.1.0}"

# Normalize path
SERVICE_PATH="${SERVICE_PATH%/}"
BASE_URL="http://${SPRITES_WORKSPACE_SERVICE_HOST}:${SPRITES_WORKSPACE_SERVICE_PORT}${SERVICE_PATH}"

PASS=0
FAIL=0

check() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local expected_key="${4:-}"

    printf "  %-40s" "$name..."

    local http_code body
    body=$(curl -sf --max-time "$SMOKE_TIMEOUT" -w '\n%{http_code}' "$url" 2>/dev/null) || {
        echo "FAIL (connection error)"
        FAIL=$((FAIL + 1))
        return 1
    }

    http_code=$(echo "$body" | tail -1)
    body=$(echo "$body" | head -n -1)

    if [ "$http_code" != "$expected_status" ]; then
        echo "FAIL (expected $expected_status, got $http_code)"
        FAIL=$((FAIL + 1))
        return 1
    fi

    if [ -n "$expected_key" ]; then
        if ! echo "$body" | grep -q "\"$expected_key\""; then
            echo "FAIL (missing key: $expected_key)"
            FAIL=$((FAIL + 1))
            return 1
        fi
    fi

    echo "OK"
    PASS=$((PASS + 1))
    return 0
}

echo "=== Workspace Service Smoke Check ==="
echo "  Target: $BASE_URL"
echo "  Timeout: ${SMOKE_TIMEOUT}s"
echo ""

# ── Health checks ──
echo "Health:"
check "healthz" "$BASE_URL/healthz" 200 "status"
check "health" "$BASE_URL/health" 200 "status"

# ── Version compatibility ──
echo ""
echo "Version:"
check "meta/version" "$BASE_URL/__meta/version" 200 "version"

# Check version compatibility
VERSION_BODY=$(curl -sf --max-time "$SMOKE_TIMEOUT" "$BASE_URL/__meta/version" 2>/dev/null || echo '{}')
ACTUAL_VERSION=$(echo "$VERSION_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','unknown'))" 2>/dev/null || echo "unknown")
printf "  %-40s" "version compatibility..."
if [ "$ACTUAL_VERSION" = "unknown" ] || [ "$ACTUAL_VERSION" = "" ]; then
    echo "SKIP (version not available)"
else
    # Simple major.minor check
    ACTUAL_MAJOR=$(echo "$ACTUAL_VERSION" | cut -d. -f1)
    EXPECTED_MAJOR=$(echo "$EXPECTED_VERSION" | cut -d. -f1)
    if [ "$ACTUAL_MAJOR" = "$EXPECTED_MAJOR" ]; then
        echo "OK ($ACTUAL_VERSION)"
        PASS=$((PASS + 1))
    else
        echo "FAIL (got $ACTUAL_VERSION, expected major $EXPECTED_MAJOR)"
        FAIL=$((FAIL + 1))
    fi
fi

# ── Endpoint smoke tests ──
echo ""
echo "Endpoints:"
check "capabilities" "$BASE_URL/api/capabilities" 200 "features"
check "config" "$BASE_URL/api/config" 200 "workspace_root"
check "project" "$BASE_URL/api/project" 200 "root"
check "file tree" "$BASE_URL/api/tree" 200 "entries"
check "git status" "$BASE_URL/api/git/status" 200 "is_repo"
check "sessions list" "$BASE_URL/api/sessions" 200 "sessions"

# ── Security check: path traversal ──
echo ""
echo "Security:"
printf "  %-40s" "path traversal blocked..."
TRAVERSAL_CODE=$(curl -sf --max-time "$SMOKE_TIMEOUT" -o /dev/null -w '%{http_code}' \
    "$BASE_URL/api/tree?path=../../../etc" 2>/dev/null || echo "000")
if [ "$TRAVERSAL_CODE" = "400" ]; then
    echo "OK (400)"
    PASS=$((PASS + 1))
elif [ "$TRAVERSAL_CODE" = "000" ]; then
    echo "SKIP (connection error)"
else
    echo "FAIL (expected 400, got $TRAVERSAL_CODE)"
    FAIL=$((FAIL + 1))
fi

# ── Summary ──
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    echo "SMOKE CHECK FAILED"
    exit 1
fi

echo "SMOKE CHECK PASSED"
exit 0
