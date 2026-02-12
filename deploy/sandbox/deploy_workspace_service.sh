#!/usr/bin/env bash
# deploy_workspace_service.sh - Idempotent source sync + config apply
#
# Deploys the workspace service code to the sprite's service runtime path.
# Safe to run multiple times (idempotent).
#
# Required environment:
#   SPRITE_HOST         - SSH-reachable sprite hostname or IP
#   SPRITES_API_TOKEN   - Auth token (used for health check only)
#
# Optional environment:
#   SERVICE_ROOT        - Service install path (default: /srv/workspace-api)
#   WORKSPACE_ROOT      - User workspace path (default: /home/sprite/workspace)
#   SECRETS_DIR         - Secrets directory (default: /home/sprite/.auth)
#   SERVICE_USER        - User to own service files (default: sprite)
#   SOURCE_DIR          - Local source directory to sync (default: src/back)
#
set -euo pipefail

# ── Configuration ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

SERVICE_ROOT="${SERVICE_ROOT:-/srv/workspace-api}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-/home/sprite/workspace}"
SECRETS_DIR="${SECRETS_DIR:-/home/sprite/.auth}"
SERVICE_USER="${SERVICE_USER:-sprite}"
SOURCE_DIR="${SOURCE_DIR:-$REPO_ROOT/src/back}"

: "${SPRITE_HOST:?SPRITE_HOST is required}"

echo "=== Workspace Service Deploy ==="
echo "  Sprite:        $SPRITE_HOST"
echo "  Service root:  $SERVICE_ROOT"
echo "  Workspace:     $WORKSPACE_ROOT"
echo "  Source:        $SOURCE_DIR"
echo ""

# ── Validate local source ──
if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: Source directory not found: $SOURCE_DIR" >&2
    exit 1
fi

# ── Ensure remote directories ──
echo "[1/4] Ensuring remote directory layout..."
ssh "$SPRITE_HOST" bash -s <<REMOTE
set -euo pipefail
mkdir -p "$SERVICE_ROOT"
mkdir -p "$WORKSPACE_ROOT"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"
echo "  Directories OK"
REMOTE

# ── Sync source ──
echo "[2/4] Syncing source to $SPRITE_HOST:$SERVICE_ROOT..."
rsync -az --delete \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    "$SOURCE_DIR/" \
    "$SPRITE_HOST:$SERVICE_ROOT/src/"
echo "  Source synced"

# ── Sync requirements/config ──
echo "[3/4] Syncing configuration files..."
# Sync pyproject.toml for dependency info
if [ -f "$REPO_ROOT/pyproject.toml" ]; then
    rsync -az "$REPO_ROOT/pyproject.toml" "$SPRITE_HOST:$SERVICE_ROOT/"
fi
echo "  Config synced"

# ── Set ownership ──
echo "[4/4] Setting file ownership..."
ssh "$SPRITE_HOST" bash -s <<REMOTE
set -euo pipefail
chown -R "$SERVICE_USER:$SERVICE_USER" "$SERVICE_ROOT" 2>/dev/null || true
chown -R "$SERVICE_USER:$SERVICE_USER" "$WORKSPACE_ROOT" 2>/dev/null || true
echo "  Ownership set"
REMOTE

echo ""
echo "=== Deploy complete ==="
echo "  Run restart_workspace_service.sh to start/restart the service"
