#!/usr/bin/env bash
# restart_workspace_service.sh - Start or restart the workspace service
#
# Starts the workspace service via Sprites Services command, or restarts
# it if already running.
#
# Required environment:
#   SPRITE_HOST                       - SSH-reachable sprite hostname or IP
#   SPRITES_WORKSPACE_SERVICE_PORT    - Port for the workspace service
#
# Optional environment:
#   SERVICE_ROOT        - Service install path (default: /srv/workspace-api)
#   WORKSPACE_ROOT      - User workspace path (default: /home/sprite/workspace)
#   SERVICE_USER        - User to run service as (default: sprite)
#   SERVICE_BIND        - Bind address (default: 0.0.0.0)
#   SERVICE_WORKERS     - Number of uvicorn workers (default: 1)
#
set -euo pipefail

SERVICE_ROOT="${SERVICE_ROOT:-/srv/workspace-api}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/home/sprite/workspace}"
SERVICE_USER="${SERVICE_USER:-sprite}"
SERVICE_BIND="${SERVICE_BIND:-0.0.0.0}"
SERVICE_WORKERS="${SERVICE_WORKERS:-1}"

: "${SPRITE_HOST:?SPRITE_HOST is required}"
: "${SPRITES_WORKSPACE_SERVICE_PORT:?SPRITES_WORKSPACE_SERVICE_PORT is required}"

echo "=== Workspace Service Restart ==="
echo "  Sprite:  $SPRITE_HOST"
echo "  Port:    $SPRITES_WORKSPACE_SERVICE_PORT"
echo "  Workers: $SERVICE_WORKERS"
echo ""

# ── Stop existing service ──
echo "[1/2] Stopping existing service (if running)..."
ssh "$SPRITE_HOST" bash -s <<REMOTE
set -euo pipefail
# Find and stop existing workspace service process
pkill -f "uvicorn.*boring_ui" 2>/dev/null && echo "  Stopped existing process" || echo "  No existing process"
sleep 1
REMOTE

# ── Start service ──
echo "[2/2] Starting workspace service..."
ssh "$SPRITE_HOST" bash -s <<REMOTE
set -euo pipefail
cd "$SERVICE_ROOT"

export PYTHONPATH="$SERVICE_ROOT/src:\$PYTHONPATH"
export WORKSPACE_ROOT="$WORKSPACE_ROOT"

nohup python3 -m uvicorn boring_ui.api.app:app \
    --host "$SERVICE_BIND" \
    --port "$SPRITES_WORKSPACE_SERVICE_PORT" \
    --workers "$SERVICE_WORKERS" \
    --log-level info \
    > "$SERVICE_ROOT/service.log" 2>&1 &

echo "  PID: \$!"
sleep 2

# Quick check that process is running
if kill -0 \$! 2>/dev/null; then
    echo "  Service started successfully"
else
    echo "ERROR: Service failed to start. Check $SERVICE_ROOT/service.log" >&2
    tail -20 "$SERVICE_ROOT/service.log" 2>/dev/null || true
    exit 1
fi
REMOTE

echo ""
echo "=== Restart complete ==="
echo "  Run smoke_check.sh to validate"
