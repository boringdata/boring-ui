#!/usr/bin/env bash
# smoke_ts_server.sh — Start the TS server locally and run smoke tests against it.
#
# Pre-validates Python smoke test parity before staging deployment.
# Runs the health and capabilities smoke suites (no auth needed).
#
# Usage:
#   ./scripts/smoke_ts_server.sh                    # Default: health + capabilities
#   ./scripts/smoke_ts_server.sh --suites health    # Specific suites
#   ./scripts/smoke_ts_server.sh --port 9000        # Custom port
#
# Requirements:
#   - Node.js 20+ with tsx installed (npm install)
#   - Python 3 with httpx (pip install httpx)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PORT="${PORT:-9876}"
SUITES="${1:---suites health,capabilities}"
TS_SERVER_PID=""

cleanup() {
  if [ -n "$TS_SERVER_PID" ] && kill -0 "$TS_SERVER_PID" 2>/dev/null; then
    echo "[smoke-ts] Stopping TS server (PID $TS_SERVER_PID)..."
    kill "$TS_SERVER_PID" 2>/dev/null || true
    wait "$TS_SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "[smoke-ts] Starting TS server on port $PORT..."

cd "$PROJECT_ROOT"

# Start the TS server in the background
PORT=$PORT \
  WORKSPACE_BACKEND=bwrap \
  CONTROL_PLANE_PROVIDER=local \
  npx tsx src/server/index.ts &
TS_SERVER_PID=$!

# Wait for server to be ready
echo "[smoke-ts] Waiting for server to start..."
for i in $(seq 1 30); do
  if curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; then
    echo "[smoke-ts] Server ready on port $PORT"
    break
  fi
  if ! kill -0 "$TS_SERVER_PID" 2>/dev/null; then
    echo "[smoke-ts] ERROR: Server process died during startup"
    exit 1
  fi
  sleep 1
done

# Verify server is actually running
if ! curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; then
  echo "[smoke-ts] ERROR: Server failed to start within 30 seconds"
  exit 1
fi

# Show health response
echo "[smoke-ts] Health check response:"
curl -s "http://localhost:$PORT/health" | python3 -m json.tool 2>/dev/null || true
echo

# Show capabilities response
echo "[smoke-ts] Capabilities check:"
curl -s "http://localhost:$PORT/api/capabilities" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'  version: {d.get(\"version\")}')
features = d.get('features', {})
enabled = [k for k, v in features.items() if v]
print(f'  enabled features: {enabled}')
print(f'  agents: {d.get(\"agents\", [])}')
print(f'  agent_mode: {d.get(\"agent_mode\")}')
print(f'  routers: {len(d.get(\"routers\", []))}')
" 2>/dev/null || true
echo

# Run smoke tests
echo "[smoke-ts] Running smoke tests..."
python3 tests/smoke/run_all.py \
  --base-url "http://localhost:$PORT" \
  --auth-mode dev \
  $SUITES

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
  echo "[smoke-ts] ALL SMOKE TESTS PASSED against TS server"
else
  echo "[smoke-ts] SMOKE TESTS FAILED (exit code $EXIT_CODE)"
fi

exit $EXIT_CODE
