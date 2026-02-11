#!/bin/bash
set -e

echo "🚀 Starting Boring UI - Agent Chat Working Setup"
echo "================================================="
echo ""

# Kill all existing processes
echo "Cleaning up old processes..."
pkill -f "uvicorn\|vite\|create_app" 2>/dev/null || true
sleep 3

cd /home/ubuntu/projects/boring-ui

# Get API key
echo "Getting API key from Vault..."
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic 2>/dev/null)

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "❌ Failed to get API key"
  exit 1
fi

echo "✅ API key loaded"
echo ""

# Start backend
echo "🔥 Starting Backend with API Key..."
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python3 -c "
from boring_ui.api.app import create_app
import uvicorn
import os

print('Backend starting with API key...')
app = create_app(include_sandbox=True, include_companion=True)
uvicorn.run(app, host='0.0.0.0', port=8000, log_level='error')
" > /tmp/backend.log 2>&1 &

BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"

# Wait for backend
echo "⏳ Waiting for backend to be ready..."
for i in {1..20}; do
  if curl -s http://localhost:8000/api/capabilities > /dev/null 2>&1; then
    echo "✅ Backend ready"
    break
  fi
  sleep 1
done
echo ""

# Start frontend
echo "🎨 Starting Frontend (Vite)..."
npx vite --host 0.0.0.0 --port 5173 > /tmp/vite.log 2>&1 &

FRONTEND_PID=$!
echo "✅ Frontend started (PID: $FRONTEND_PID)"

# Wait for frontend
echo "⏳ Waiting for frontend to be ready..."
for i in {1..30}; do
  if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Frontend ready"
    break
  fi
  sleep 1
done
echo ""

echo "=========================================="
echo "✅ BORING UI IS RUNNING!"
echo "=========================================="
echo ""
echo "🌐 Open in browser: http://localhost:5173"
echo ""
echo "✅ Agent chat should NOW respond to messages"
echo "✅ API key is configured"
echo "✅ Both backend and frontend running"
echo ""
echo "📝 To test:"
echo "   1. Click the chat input (right pane)"
echo "   2. Type: 'Hello Claude'"
echo "   3. Press Enter"
echo "   4. Claude should respond within 1-2 seconds"
echo ""
echo "🛑 To stop: Press Ctrl+C"
echo ""

# Keep running
wait
