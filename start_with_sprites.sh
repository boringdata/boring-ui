#!/bin/bash
set -e

echo "🚀 Starting Boring UI with Sprites.dev Sandbox"
echo "=============================================="
echo ""

# Get Sprites credentials from Vault
echo "📦 Loading Sprites.dev credentials..."
SPRITES_API_KEY=$(vault kv get -field=api_key secret/agent/sprites 2>/dev/null)
SPRITES_API_SECRET=$(vault kv get -field=api_secret secret/agent/sprites 2>/dev/null)
SPRITES_ACCOUNT_ID=$(vault kv get -field=account_id secret/agent/sprites 2>/dev/null)
SPRITES_USERNAME=$(vault kv get -field=username secret/agent/sprites 2>/dev/null)

if [ -z "$SPRITES_API_KEY" ]; then
  echo "❌ Failed to get Sprites credentials from Vault"
  exit 1
fi

echo "✅ Sprites credentials loaded"
echo "   Account: $SPRITES_ACCOUNT_ID"
echo "   Username: $SPRITES_USERNAME"
echo ""

# Get Claude API key
echo "🔑 Loading Claude API key..."
ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic 2>/dev/null)
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "❌ Failed to get Claude API key from Vault"
  exit 1
fi
echo "✅ Claude API key loaded"
echo ""

# Start backend in background
echo "🔥 Starting Backend (FastAPI)..."
export SANDBOX_PROVIDER=sprites
export SPRITES_API_KEY="$SPRITES_API_KEY"
export SPRITES_API_SECRET="$SPRITES_API_SECRET"
export ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY"

cd /home/ubuntu/projects/boring-ui

# Start backend with Python
python3 -c "
from boring_ui.api.app import create_app
import uvicorn

app = create_app(include_sandbox=True, include_companion=True)
uvicorn.run(app, host='0.0.0.0', port=8000)
" &

BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"
echo ""

# Wait for backend to be ready
echo "⏳ Waiting for backend to be ready..."
for i in {1..30}; do
  if curl -s http://localhost:8000/api/capabilities > /dev/null 2>&1; then
    echo "✅ Backend is ready!"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "❌ Backend failed to start"
    kill $BACKEND_PID
    exit 1
  fi
  sleep 1
done
echo ""

# Test backend endpoints
echo "🧪 Testing backend endpoints..."
echo "   GET /api/capabilities..."
curl -s http://localhost:8000/api/capabilities | jq '.features | {chat_claude_code, sandbox, companion}' 2>/dev/null

echo ""
echo "   GET /api/sandbox/status..."
curl -s http://localhost:8000/api/sandbox/status | jq '.' 2>/dev/null
echo ""

# Start frontend
echo "🎨 Starting Frontend (Vite)..."
npx vite --host 0.0.0.0 --port 5173 &

FRONTEND_PID=$!
echo "✅ Frontend started (PID: $FRONTEND_PID)"
echo ""

# Wait for frontend
echo "⏳ Waiting for frontend to be ready..."
for i in {1..30}; do
  if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Frontend is ready!"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "❌ Frontend failed to start"
    kill $BACKEND_PID $FRONTEND_PID
    exit 1
  fi
  sleep 1
done
echo ""

# Display information
echo "=========================================="
echo "✅ BORING UI WITH SPRITES.DEV IS RUNNING!"
echo "=========================================="
echo ""
echo "🌐 Frontend: http://localhost:5173"
echo "🔌 Backend:  http://localhost:8000"
echo ""
echo "📋 Configuration:"
echo "   Sandbox Provider: Sprites.dev"
echo "   Account: $SPRITES_ACCOUNT_ID ($SPRITES_USERNAME)"
echo "   Agent: Claude Code (right pane)"
echo ""
echo "🎯 What to do:"
echo "   1. Open http://localhost:5173 in your browser"
echo "   2. You should see FILES from your Sprites sandbox"
echo "   3. Type a message in the chat (right pane)"
echo "   4. The Agent (Claude) will respond"
echo "   5. The agent can access files in the Sprites sandbox"
echo ""
echo "🛑 To stop: Press Ctrl+C"
echo ""

# Keep processes running
wait
