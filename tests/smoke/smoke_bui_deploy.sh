#!/usr/bin/env bash
# smoke_bui_deploy.sh — End-to-end smoke test for bui deploy
#
# Tests the full deployed app: auth, files, git, control-plane, capabilities.
# Run after `bui deploy`:
#   bash tests/smoke/smoke_bui_deploy.sh [BASE_URL]
#
set -euo pipefail

BASE="${1:-https://julien-hurault--boring-ui-web.modal.run}"
COOKIES=$(mktemp)
PASS=0
FAIL=0
TOTAL=0

cleanup() { rm -f "$COOKIES"; }
trap cleanup EXIT

check() {
  local name="$1" expected="$2" actual="$3"
  TOTAL=$((TOTAL + 1))
  if echo "$actual" | grep -q "$expected"; then
    echo "  PASS  $name"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $name (expected: $expected)"
    echo "        got: $(echo "$actual" | head -1)"
    FAIL=$((FAIL + 1))
  fi
}

check_status() {
  local name="$1" expected="$2" actual="$3"
  TOTAL=$((TOTAL + 1))
  if [ "$actual" = "$expected" ]; then
    echo "  PASS  $name (HTTP $actual)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL  $name (expected HTTP $expected, got $actual)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== boring-ui deploy smoke test ==="
echo "    target: $BASE"
echo ""

# ── 1. Frontend ───────────────────────────────────────────
echo "[1/9] Frontend"
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/" 2>&1)
check_status "GET /" "200" "$status"

html=$(curl -s "$BASE/" 2>&1)
check "HTML has root div" 'id="root"' "$html"

# ── 2. Capabilities ──────────────────────────────────────
echo "[2/9] Capabilities"
caps=$(curl -s "$BASE/api/capabilities" 2>&1)
check "capabilities returns JSON" '"version"' "$caps"
check "auth provider is neon" '"provider":"neon"' "$(echo "$caps" | tr -d ' ')"
check "neonAuthUrl set" '"neonAuthUrl"' "$caps"
check "files router enabled" '"files"' "$caps"
check "git router enabled" '"git"' "$caps"
check "control_plane enabled" '"control_plane"' "$caps"
check "pty enabled" '"pty"' "$caps"
check "chat enabled" '"chat_claude_code"' "$caps"

# ── 3. Config ────────────────────────────────────────────
echo "[3/9] Config"
cfg=$(curl -s "$BASE/api/config" 2>&1)
check "config returns workspace_root" '"workspace_root"' "$cfg"

# ── 4. Auth — Login page ────────────────────────────────
echo "[4/9] Auth pages"
login_status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/auth/login" 2>&1)
check_status "GET /auth/login" "200" "$login_status"

# ── 5. Auth — Signup + Signin ────────────────────────────
echo "[5/9] Auth flow"
EMAIL="smoke-$(date +%s)@boringdata.io"
PASS_STR="SmokeTest$(date +%s)"

signup=$(curl -s -X POST "$BASE/auth/sign-up" \
  -H "Content-Type: application/json" \
  -H "Origin: $BASE" \
  --data-raw "{\"email\":\"$EMAIL\",\"password\":\"$PASS_STR\",\"name\":\"Smoke Test\"}" 2>&1)
check "signup ok" '"ok":true' "$signup"
check "signup needs verification" 'requires_email_verification' "$signup"

signin=$(curl -s -X POST "$BASE/auth/sign-in" \
  -H "Content-Type: application/json" \
  -H "Origin: $BASE" \
  -c "$COOKIES" \
  --data-raw "{\"email\":\"$EMAIL\",\"password\":\"$PASS_STR\"}" 2>&1)
check "signin ok" '"ok":true' "$signin"

cookie_check=$(grep -c "boring_session" "$COOKIES" 2>/dev/null || echo "0")
check "session cookie set" "1" "matches: $cookie_check"

# ── 6. Auth — /me ────────────────────────────────────────
echo "[6/9] Authenticated user"
me=$(curl -s -b "$COOKIES" "$BASE/api/v1/me" 2>&1)
check "/me returns ok" '"ok":true' "$me"
check "/me has email" "$EMAIL" "$me"
check "/me has user_id" '"user_id"' "$me"

# ── 7. Files API ─────────────────────────────────────────
echo "[7/9] Files API"
TESTFILE="smoke-test-$(date +%s).txt"
TESTCONTENT="smoke test content $(date)"

write=$(curl -s -X PUT -b "$COOKIES" "$BASE/api/v1/files/write?path=$TESTFILE" \
  -H "Content-Type: application/json" \
  --data-raw "{\"content\":\"$TESTCONTENT\"}" 2>&1)
check "write file" '"success":true' "$write"

read_resp=$(curl -s -b "$COOKIES" "$BASE/api/v1/files/read?path=$TESTFILE" 2>&1)
check "read file" "$TESTCONTENT" "$read_resp"

list=$(curl -s -b "$COOKIES" "$BASE/api/v1/files/list?path=." 2>&1)
check "list contains file" "$TESTFILE" "$list"

del=$(curl -s -X DELETE -b "$COOKIES" "$BASE/api/v1/files/delete?path=$TESTFILE" 2>&1)
check "delete file" "success" "$del"

# ── 8. Git API ───────────────────────────────────────────
echo "[8/9] Git API"
git_status=$(curl -s -b "$COOKIES" "$BASE/api/v1/git/status" 2>&1)
check "git status returns" '"available":true' "$git_status"

# ── 9. Control Plane ─────────────────────────────────────
echo "[9/9] Control Plane"
cp_health=$(curl -s -b "$COOKIES" "$BASE/api/v1/control-plane/health" 2>&1)
check "control-plane health ok" '"ok":true' "$cp_health"

cp_workspaces=$(curl -s -b "$COOKIES" "$BASE/api/v1/control-plane/workspaces" 2>&1)
check "workspaces list ok" '"ok":true' "$cp_workspaces"

# ── Summary ──────────────────────────────────────────────
echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
if [ $FAIL -gt 0 ]; then
  echo "SMOKE TEST FAILED"
  exit 1
else
  echo "ALL TESTS PASSED"
  exit 0
fi
