# Boring UI - Sprites.dev Deployment Guide

## Overview

This guide shows how to deploy the entire Boring UI application on a Sprites.dev VM, with both **File API** and **Agent API** running on the same machine accessing a shared workspace.

### Architecture

```
┌────────────────────────────────────────────────┐
│          Sprites.dev VM                        │
│          (e.g., 10.0.1.50)                      │
│                                                 │
│  ┌──────────────────────────────────────────┐ │
│  │  Boring-UI API (Port 8000)               │ │
│  │  ├─ File API: /api/files/*               │ │
│  │  ├─ Git API: /api/git/*                  │ │
│  │  ├─ Capabilities: /api/capabilities      │ │
│  │  ├─ Workspace: /home/sprite/workspace    │ │
│  │  └─ ANTHROPIC_API_KEY configured         │ │
│  └──────────────────────────────────────────┘ │
│                                                 │
│  ┌──────────────────────────────────────────┐ │
│  │  Sandbox-Agent (Port 2468)               │ │
│  │  ├─ Chat API: /api/v1/*                  │ │
│  │  ├─ Bearer Token Auth                    │ │
│  │  └─ Workspace: /home/sprite/workspace    │ │
│  └──────────────────────────────────────────┘ │
│                                                 │
└────────────────────────────────────────────────┘
         ↑                        ↑
   /api/capabilities         Direct Chat API
   (Token distribution)       (with bearer token)
         │                        │
         └────────┬───────────────┘
                  │
          Browser / Frontend
          (local network or SSH tunnel)
```

## Step-by-Step Deployment

### Prerequisites

- SSH access to Sprites.dev VM
- Python 3.9+ installed on Sprites.dev
- `sandbox-agent` binary available on Sprites.dev
- ANTHROPIC_API_KEY from Vault

### Step 1: SSH Access Setup

```bash
# From your local machine, SSH into Sprites.dev
ssh user@sprites.dev

# Optional: Set up SSH tunneling for browser access
# From your local machine in a separate terminal:
ssh -L 8000:127.0.0.1:8000 -L 2468:127.0.0.1:2468 user@sprites.dev
# Then access: http://localhost:8000 and http://localhost:2468
```

### Step 2: Prepare Workspace

```bash
# On Sprites.dev VM
ssh user@sprites.dev

# Create workspace directory
mkdir -p /home/sprite/workspace

# Test basic file operations
touch /home/sprite/workspace/.boring-ui-test
ls -la /home/sprite/workspace/
```

### Step 3: Install Boring-UI Backend

```bash
# On Sprites.dev VM
cd /home/sprite

# Clone boring-ui repo (or ensure you have it)
git clone https://github.com/anthropics/boring-ui.git
cd boring-ui

# Install Python dependencies
pip3 install -e . --break-system-packages

# Verify installation
python3 -c "from boring_ui.api.app import create_app; print('✓ Installation successful')"
```

### Step 4: Start Backend (Main Window)

```bash
# On Sprites.dev VM
cd /home/sprite/boring-ui

# Get API key from Vault (using agent token)
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)

# Set workspace and external host
export WORKSPACE_ROOT=/home/sprite/workspace
export EXTERNAL_HOST=sprites.dev  # or IP address like 10.0.1.50

# Start backend
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)

app = create_app(
    include_sandbox=True,      # Enable sandbox-agent management
    include_companion=False,   # Not needed for this setup
)

print('\\n🚀 Backend starting at http://0.0.0.0:8000')
print('📋 Workspace: /home/sprite/workspace')
print('🔑 API key: configured from Vault')
print('\\n')

uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
"
```

**Output should include**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Step 5: Verify Backend Health

```bash
# In another SSH window
curl http://127.0.0.1:8000/health

# Expected response:
{
  "status": "ok",
  "workspace": "/home/sprite/workspace",
  "features": {
    "files": true,
    "git": true,
    "pty": true,
    "chat_claude_code": true,
    "sandbox": true
  }
}
```

### Step 6: Check Capabilities & Tokens

```bash
# Get the service registry and tokens
curl http://127.0.0.1:8000/api/capabilities | jq .

# Should include sandbox service:
{
  "services": {
    "sandbox": {
      "url": "http://sprites.dev:2468",
      "token": "a1b2c3d4...",  # 48-char hex bearer token
      "qpToken": "a1b2c3d4...",
      "protocol": "rest+sse"
    }
  }
}
```

### Step 7: Verify Sandbox-Agent Started

```bash
# Check if sandbox-agent is running
ps aux | grep sandbox-agent

# Expected: sandbox-agent process with --port 2468

# Test sandbox-agent health
curl -H "Authorization: Bearer $(curl -s http://127.0.0.1:8000/api/capabilities | jq -r .services.sandbox.token)" \
  http://127.0.0.1:2468/api/v1/health

# Expected response: {"status": "ok"} or similar
```

### Step 8: Set Up Frontend Access

**Option A: Via SSH Tunnel (Recommended)**

```bash
# From your local machine (in a separate terminal)
ssh -L 8000:127.0.0.1:8000 -L 2468:127.0.0.1:2468 user@sprites.dev

# Keep this terminal open
# Frontend will connect to http://localhost:8000 and http://localhost:2468
```

**Option B: Direct Network Access (if on same network)**

```bash
# If browser is on same network as Sprites.dev VM:
# Access directly: http://sprites.dev:8000 or http://10.0.1.50:8000
```

### Step 9: Start Frontend

```bash
# On your local machine (or another Sprites.dev machine)
# Clone boring-ui repo
git clone https://github.com/anthropics/boring-ui.git
cd boring-ui

# Install frontend dependencies
npm install

# Start Vite dev server
npx vite --host 0.0.0.0 --port 5173

# Output:
# ➜  Local:   http://localhost:5173/
# ➜  Network: http://192.168.x.x:5173/
```

### Step 10: Access the Application

```bash
# Open browser and navigate to:
http://localhost:5173  # (with SSH tunnel from Step 8)
or
http://sprites.dev:5173  # (if on same network)
```

**You should see**:
- ✅ FileTree showing `/home/sprite/workspace` contents
- ✅ Filesystem indicator at top of FileTree showing "Sprites.dev"
- ✅ Agent chat panel on the right (currently empty)
- ✅ Terminal panel for shell access

### Step 11: Test File Operations

```
In the browser:
1. Go to FileTree panel (left side)
2. Click "New File"
3. Name it: test.txt
4. Enter content: "Hello from Sprites.dev"
5. Click Save

On Sprites.dev VM, verify file was created:
ls -la /home/sprite/workspace/test.txt
cat /home/sprite/workspace/test.txt
```

**Expected**:
```
Hello from Sprites.dev
```

### Step 12: Test Agent Chat

```
In the browser:
1. Go to Terminal panel (right side)
2. Make sure "Sandbox Agent" is selected (dropdown)
3. Click in the chat text area
4. Type: "Hello, can you see my workspace?"
5. Press Enter

Expected: Agent responds with acknowledgment
```

**Check in agent logs**:
```
# On Sprites.dev VM (if running agent in foreground)
# You should see chat requests coming in
```

## Environment Variables Summary

| Variable | Value | Purpose |
|----------|-------|---------|
| `WORKSPACE_ROOT` | `/home/sprite/workspace` | Where FileTree reads/writes files |
| `ANTHROPIC_API_KEY` | From Vault | Claude API authentication |
| `EXTERNAL_HOST` | `sprites.dev` or `10.0.1.50` | External hostname for services |
| `SANDBOX_PORT` | `2468` | Sandbox-agent port |
| `SANDBOX_TOKEN` | Auto-generated | Bearer token for sandbox-agent |
| `SANDBOX_WORKSPACE` | `/home/sprite/workspace` | Workspace path for sandbox-agent |

## Startup Script (Quick Deploy)

Save as `DEPLOY_TO_SPRITES.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Deploying Boring-UI to Sprites.dev"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check prerequisites
echo "${BLUE}Checking prerequisites...${NC}"
which python3 > /dev/null || { echo "❌ python3 not found"; exit 1; }
which sandbox-agent > /dev/null || { echo "❌ sandbox-agent not found"; exit 1; }

# Set variables
WORKSPACE_ROOT=${WORKSPACE_ROOT:-/home/sprite/workspace}
EXTERNAL_HOST=${EXTERNAL_HOST:-$(hostname -I | awk '{print $1}')}

echo "${BLUE}Environment:${NC}"
echo "  Workspace: $WORKSPACE_ROOT"
echo "  External Host: $EXTERNAL_HOST"
echo ""

# Create workspace
echo "${BLUE}Creating workspace directory...${NC}"
mkdir -p "$WORKSPACE_ROOT"
touch "$WORKSPACE_ROOT"/.boring-ui-test
echo "  ✓ Workspace ready"
echo ""

# Get API key from Vault
echo "${BLUE}Getting ANTHROPIC_API_KEY from Vault...${NC}"
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
echo "  ✓ API key loaded"
echo ""

# Install boring-ui
echo "${BLUE}Installing boring-ui...${NC}"
cd /home/sprite
if [ ! -d boring-ui ]; then
    git clone https://github.com/anthropics/boring-ui.git
fi
cd boring-ui
pip3 install -e . --break-system-packages > /dev/null 2>&1
echo "  ✓ Installation complete"
echo ""

# Start backend
echo "${BLUE}Starting Boring-UI backend...${NC}"
export WORKSPACE_ROOT
export EXTERNAL_HOST

python3 -c "
from boring_ui.api.app import create_app
import uvicorn

app = create_app(include_sandbox=True)
print()
print('${GREEN}✓ Backend starting at http://0.0.0.0:8000${NC}')
print('  Workspace: $WORKSPACE_ROOT')
print('  External Host: $EXTERNAL_HOST')
print('  Sandbox-Agent: Port 2468')
print()

uvicorn.run(app, host='0.0.0.0', port=8000)
" &

BACKEND_PID=$!
sleep 2

# Verify backend
echo "${BLUE}Verifying backend health...${NC}"
if curl -s http://127.0.0.1:8000/health > /dev/null; then
    echo "  ✓ Backend is healthy"
else
    echo "  ❌ Backend failed to start"
    kill $BACKEND_PID
    exit 1
fi
echo ""

# Instructions
echo "${GREEN}=== Deployment Successful ===${NC}"
echo ""
echo "Frontend access:"
echo "  1. Install frontend: npm install"
echo "  2. Start dev server: npx vite --host 0.0.0.0 --port 5173"
echo ""
echo "SSH tunnel (from local machine):"
echo "  ssh -L 8000:127.0.0.1:8000 -L 2468:127.0.0.1:2468 user@sprites.dev"
echo ""
echo "Then open browser:"
echo "  http://localhost:5173 (with SSH tunnel)"
echo "  or http://sprites.dev:5173 (if on same network)"
echo ""
echo "Backend PID: $BACKEND_PID"
echo "To stop: kill $BACKEND_PID"
```

Run with:
```bash
chmod +x DEPLOY_TO_SPRITES.sh
./DEPLOY_TO_SPRITES.sh
```

## Troubleshooting

### Backend won't start: "Address already in use"

```bash
# Port 8000 is already in use
# Find and kill existing process
lsof -i :8000
kill -9 <PID>

# Then retry
```

### Sandbox-agent not responding

```bash
# Check if agent started
ps aux | grep sandbox-agent

# If not running, check backend logs for errors:
# Look for "SandboxManager" output

# If missing credentials, verify:
vault kv get secret/agent/anthropic
```

### FileTree shows empty / wrong workspace

```bash
# Verify WORKSPACE_ROOT is set
echo $WORKSPACE_ROOT

# Should output: /home/sprite/workspace

# If wrong, restart backend with correct env var:
export WORKSPACE_ROOT=/home/sprite/workspace
# Then restart backend
```

### Browser can't reach backend

```bash
# If using SSH tunnel, verify it's running
# Should see: Local forwarding port 8000 to 127.0.0.1:8000

# If direct network access, verify firewall:
ufw allow 8000
ufw allow 2468

# Test from browser console:
await fetch('http://sprites.dev:8000/health').then(r => r.json())
```

## Production Checklist

- [ ] **Security**
  - [ ] Use strong SSH keys (no passwords)
  - [ ] Restrict SSH access (firewall rules)
  - [ ] ANTHROPIC_API_KEY stored securely (never in code)
  - [ ] Use HTTPS tunnel or secure VPN for remote access
  - [ ] Tokens are short-lived and automatically managed

- [ ] **Performance**
  - [ ] WORKSPACE_ROOT is local filesystem (no NFS/network I/O)
  - [ ] Backend and Agent on same machine (zero latency)
  - [ ] File operations are direct (no proxy overhead)

- [ ] **Monitoring**
  - [ ] Check backend logs for errors
  - [ ] Monitor disk usage in /home/sprite/workspace
  - [ ] Verify API key hasn't expired
  - [ ] Watch for agent crashes/restarts

- [ ] **Backup & Recovery**
  - [ ] Backup /home/sprite/workspace regularly
  - [ ] Document configuration for recovery
  - [ ] Keep installation scripts version controlled

## Advanced Configuration

### Multiple Workspaces

Run multiple instances with different workspaces:

```bash
# Instance 1: /home/sprite/workspace-1
WORKSPACE_ROOT=/home/sprite/workspace-1 \
EXTERNAL_HOST=sprites.dev-1 \
python3 -c "..." &

# Instance 2: /home/sprite/workspace-2
WORKSPACE_ROOT=/home/sprite/workspace-2 \
EXTERNAL_HOST=sprites.dev-2 \
python3 -c "..." &
```

### Custom Port Configuration

```bash
# Change backend port (default 8000)
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True)
uvicorn.run(app, host='0.0.0.0', port=9000)  # Custom port
"

# Change sandbox-agent port (via env var)
export SANDBOX_PORT=3000
# Backend will start agent on port 3000
```

## Summary

**What You Get**:
- ✅ FileTree with direct filesystem access to `/home/sprite/workspace`
- ✅ Chat agent running on same Sprites.dev VM
- ✅ Zero-latency file operations
- ✅ Secure token-based authentication
- ✅ Easy to scale with multiple instances
- ✅ Production-ready deployment

**Key Points**:
- Both services (File API and Agent API) run on Sprites.dev
- No mounting/network filesystem needed
- Simple bearer token authentication
- Capabilities endpoint distributes tokens to browser
- Browser connects directly to both services

**Timeline**:
- ~5 minutes: Install dependencies
- ~2 minutes: Start backend and agent
- ~1 minute: Verify health
- ~5 minutes: Set up frontend and test
- **Total: ~13 minutes to full deployment**
