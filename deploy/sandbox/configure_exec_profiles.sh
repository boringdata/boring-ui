#!/usr/bin/env bash
# configure_exec_profiles.sh - Set up PTY/chat exec command templates
#
# Configures the exec command profiles used by Sprites to launch
# PTY and chat sessions. These are server-owned templates with
# no client-controlled command text.
#
# Required environment:
#   SPRITE_HOST         - SSH-reachable sprite hostname or IP
#
# Optional environment:
#   WORKSPACE_ROOT      - User workspace path (default: /home/sprite/workspace)
#   EXEC_CONFIG_DIR     - Profile config directory (default: /home/sprite/.config/exec)
#   PTY_SHELL           - Shell binary for PTY sessions (default: /bin/bash)
#   CHAT_BINARY         - Chat binary path (default: claude)
#   CHAT_ARGS           - Extra args for chat (default: --dangerously-skip-permissions)
#
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/home/sprite/workspace}"
EXEC_CONFIG_DIR="${EXEC_CONFIG_DIR:-/home/sprite/.config/exec}"
PTY_SHELL="${PTY_SHELL:-/bin/bash}"
CHAT_BINARY="${CHAT_BINARY:-claude}"
CHAT_ARGS="${CHAT_ARGS:---dangerously-skip-permissions}"

: "${SPRITE_HOST:?SPRITE_HOST is required}"

echo "=== Exec Profile Configuration ==="
echo "  Sprite:        $SPRITE_HOST"
echo "  Config dir:    $EXEC_CONFIG_DIR"
echo "  PTY shell:     $PTY_SHELL"
echo "  Chat binary:   $CHAT_BINARY"
echo ""

echo "[1/2] Creating exec profile directory..."
ssh "$SPRITE_HOST" mkdir -p "$EXEC_CONFIG_DIR"

echo "[2/2] Writing exec profiles..."
ssh "$SPRITE_HOST" bash -s <<REMOTE
set -euo pipefail

# PTY shell profile
cat > "$EXEC_CONFIG_DIR/pty_shell.json" <<'PROFILE'
{
  "id": "shell",
  "description": "Interactive bash shell",
  "command": ["$PTY_SHELL"],
  "working_directory": "$WORKSPACE_ROOT",
  "env": {
    "TERM": "xterm-256color",
    "HOME": "/home/sprite"
  },
  "timeout_seconds": 3600,
  "max_output_bytes": 204800
}
PROFILE

# Chat/Claude profile
cat > "$EXEC_CONFIG_DIR/pty_claude.json" <<'PROFILE'
{
  "id": "claude",
  "description": "Claude Code assistant",
  "command": ["$CHAT_BINARY", "$CHAT_ARGS"],
  "working_directory": "$WORKSPACE_ROOT",
  "env": {
    "TERM": "xterm-256color",
    "HOME": "/home/sprite"
  },
  "timeout_seconds": 7200,
  "max_output_bytes": 1048576
}
PROFILE

echo "  Profiles written:"
ls -la "$EXEC_CONFIG_DIR/"
REMOTE

echo ""
echo "=== Exec profiles configured ==="
