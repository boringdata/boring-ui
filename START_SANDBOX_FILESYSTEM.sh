#!/bin/bash
# Start Boring UI with Sandbox Filesystem
# Files are read from / written to the sandbox workspace, not local filesystem

set -e

echo "🚀 Starting Boring UI with SANDBOX FILESYSTEM"
echo "=============================================="
echo ""

# Kill old processes
pkill -9 -f "uvicorn\|vite\|node" 2>/dev/null || true
sleep 2

cd /home/ubuntu/projects/boring-ui

# Get API key
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)

# Create sandbox workspace
SANDBOX_WORKSPACE="/tmp/sandbox-workspace"
mkdir -p "$SANDBOX_WORKSPACE"
echo "Sandbox workspace: $SANDBOX_WORKSPACE"

echo ""
echo "🎯 Backend on 0.0.0.0:8000"
echo "   FileTree workspace: $SANDBOX_WORKSPACE"
echo ""

# Start backend with sandbox filesystem
FILESYSTEM_SOURCE=sandbox SANDBOX_WORKSPACE="$SANDBOX_WORKSPACE" python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True, include_companion=False)
uvicorn.run(app, host='0.0.0.0', port=8000, log_level='error')
" > /tmp/backend.log 2>&1 &

sleep 8

# Start frontend
echo "🎨 Frontend on 0.0.0.0:5173"
npx vite --host 0.0.0.0 --port 5173 > /tmp/vite.log 2>&1 &

sleep 10

echo ""
echo "✅ Boring UI SANDBOX MODE READY"
echo "=============================================="
echo ""
echo "📍 Access: http://213.32.19.186:5173"
echo ""
echo "🔧 Configuration:"
echo "   FILESYSTEM_SOURCE=sandbox"
echo "   Workspace: $SANDBOX_WORKSPACE"
echo "   FileTree shows files from: $SANDBOX_WORKSPACE"
echo "   File creation works in: $SANDBOX_WORKSPACE"
echo ""
echo "✨ Feature: File operations are isolated to sandbox workspace"
echo ""
