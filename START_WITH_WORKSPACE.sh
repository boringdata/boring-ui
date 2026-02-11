#!/bin/bash
# Start Boring UI with configurable workspace
#
# Usage:
#   ./START_WITH_WORKSPACE.sh /home/ubuntu/projects/boring-ui
#   ./START_WITH_WORKSPACE.sh /path/on/sprites/machine
#
# The app will serve files from the specified workspace path
# File list, create, read, write operations all work on that path

WORKSPACE="${1:-.}"
WORKSPACE=$(cd "$WORKSPACE" 2>/dev/null && pwd) || {
  echo "❌ Workspace path not found: $1"
  exit 1
}

echo "🚀 Starting Boring UI"
echo "===================="
echo ""
echo "📂 Workspace: $WORKSPACE"
echo "   Files will be listed from: $WORKSPACE"
echo "   File creation will be in: $WORKSPACE"
echo "   (Whether local machine, Sprites VM, or mounted filesystem)"
echo ""

# Kill old processes
pkill -9 -f "uvicorn\|vite\|node" 2>/dev/null || true
sleep 2

cd /home/ubuntu/projects/boring-ui

# Get API key
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)

# Start backend with custom workspace
echo "🎯 Backend on 0.0.0.0:8000..."
WORKSPACE_ROOT="$WORKSPACE" python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True, include_companion=False)
uvicorn.run(app, host='0.0.0.0', port=8000, log_level='error')
" > /tmp/backend.log 2>&1 &

sleep 8

# Start frontend
echo "🎨 Frontend on 0.0.0.0:5173..."
npx vite --host 0.0.0.0 --port 5173 > /tmp/vite.log 2>&1 &

sleep 10

echo ""
echo "✅ Boring UI Ready"
echo "===================="
echo ""
echo "📍 Access: http://213.32.19.186:5173"
echo ""
echo "📂 FileTree workspace: $WORKSPACE"
echo "   ✓ List files from: $WORKSPACE"
echo "   ✓ Create files in: $WORKSPACE"
echo "   ✓ Read files from: $WORKSPACE"
echo "   ✓ Works with local, Sprites, or any filesystem"
echo ""
