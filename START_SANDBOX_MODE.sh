#!/bin/bash
# Start Boring UI in Sandbox Mode
# This starts the app with sandbox filesystem enabled

set -e

echo "🚀 Starting Boring UI in SANDBOX MODE"
echo "======================================"

# Get API key from Vault
echo "Getting ANTHROPIC_API_KEY from Vault..."
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)

# Kill old processes
echo "Cleaning up old processes..."
pkill -f "uvicorn|vite" 2>/dev/null || true
sleep 2

cd /home/ubuntu/projects/boring-ui

# Start backend with sandbox enabled
echo ""
echo "🎯 Starting Backend with SANDBOX PROVIDER..."
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True, include_companion=False)
uvicorn.run(app, host='0.0.0.0', port=8000, log_level='error')
" > /tmp/backend-sandbox.log 2>&1 &

BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

sleep 5

# Verify backend is ready
echo "Checking backend health..."
MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
  if curl -s http://localhost:8000/api/capabilities > /dev/null 2>&1; then
    echo "✅ Backend ready"
    break
  fi
  RETRY=$((RETRY + 1))
  sleep 1
done

# Start frontend on 0.0.0.0
echo ""
echo "🎨 Starting Frontend on 0.0.0.0:5173..."
npx vite --host 0.0.0.0 --port 5173 > /tmp/vite-sandbox.log 2>&1 &

FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

sleep 8

echo ""
echo "======================================"
echo "✅ Boring UI SANDBOX MODE READY"
echo "======================================"
echo ""
echo "📍 Access at: http://0.0.0.0:5173"
echo "📍 Or locally: http://localhost:5173"
echo ""
echo "🔧 Backend: http://0.0.0.0:8000"
echo "📦 Sandbox Agent: http://localhost:2468"
echo ""
echo "📝 Logs:"
echo "   Backend: tail -f /tmp/backend-sandbox.log"
echo "   Frontend: tail -f /tmp/vite-sandbox.log"
echo ""
echo "⏹️  To stop: pkill -f 'uvicorn\|vite'"
echo ""

# Keep script running
wait $BACKEND_PID
