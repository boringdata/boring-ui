# Getting Started: Sprites + Chat

Complete guide to run the boring-ui example app with Sprites.dev as the sandbox provider.

## ⚡ Quick Start (5 minutes)

### 1. Set Credentials
```bash
export SPRITES_TOKEN=$(vault kv get -field=api_token secret/agent/boringdata-agent)
export SPRITES_ORG=$(vault kv get -field=sprites_org secret/agent/boringdata-agent)
```

### 2. Start Everything
```bash
cd /home/ubuntu/projects/boring-ui
chmod +x examples/start.sh
./examples/start.sh
```

### 3. Open Browser
- **App**: http://localhost:5173
- **Sandbox Chat**: http://localhost:5173?chat=sandbox
- **Dashboard**: file://localhost:5173/examples/sprites_chat_demo.html

Done! ✅

---

## 📦 What's Included

The `examples/` directory contains:

| File | Purpose |
|------|---------|
| `start.sh` | Main launcher (recommended) |
| `sprites_chat_example.py` | Python startup script with validation |
| `test_sprites_chat_integration.py` | Integration test with Sprites API |
| `sprites_chat_demo.html` | Interactive dashboard |
| `README.md` | Detailed documentation |
| `GETTING_STARTED.md` | This file |

---

## 🚀 Running the App

### Option 1: Using the Bash Script (RECOMMENDED)

```bash
./examples/start.sh
```

Features:
- ✅ Auto-loads credentials from Vault
- ✅ Installs dependencies
- ✅ Starts backend + frontend
- ✅ Shows quick links and API examples

### Option 2: Using the Python Script

```bash
export SPRITES_TOKEN="..."
export SPRITES_ORG="..."
python3 examples/sprites_chat_example.py
```

Features:
- ✅ Verbose logging
- ✅ Checks all requirements before starting
- ✅ Auto-installs npm/pip dependencies
- ✅ Pretty output with status badges

### Option 3: Manual Startup

**Terminal 1 - Backend:**
```bash
export SANDBOX_PROVIDER=sprites
export SPRITES_TOKEN=$(vault kv get -field=api_token secret/agent/boringdata-agent)
export SPRITES_ORG=$(vault kv get -field=sprites_org secret/agent/boringdata-agent)

python3 -c "
from boring_ui.api.app import create_app
import uvicorn

app = create_app(include_sandbox=True, include_companion=True)
uvicorn.run(app, host='0.0.0.0', port=8000)
"
```

**Terminal 2 - Frontend:**
```bash
npx vite --host 0.0.0.0 --port 5173
```

---

## 🎮 Using the App

### Via Browser

**Main UI:**
```
http://localhost:5173
```

**Sandbox Chat:**
```
http://localhost:5173?chat=sandbox
```

**Companion Chat:**
```
http://localhost:5173?chat=companion
```

**Interactive Dashboard:**
```
file:///home/ubuntu/projects/boring-ui/examples/sprites_chat_demo.html
```

### Via API

Start sandbox:
```bash
curl -X POST http://localhost:8000/api/sandbox/start
```

Check status:
```bash
curl http://localhost:8000/api/sandbox/status
```

Get logs:
```bash
curl http://localhost:8000/api/sandbox/logs?limit=20
```

Stream logs:
```bash
curl http://localhost:8000/api/sandbox/logs/stream
```

See all endpoints:
```bash
curl http://localhost:8000/api/capabilities
```

---

## 🧪 Testing

### Run Integration Test
```bash
./examples/start.sh --test
```

This will:
1. ✅ Check backend is running
2. ✅ Fetch capabilities
3. ✅ Check sandbox status
4. ✅ Start a new sandbox
5. ✅ Wait for it to be healthy
6. ✅ Get logs and metrics
7. ✅ Print summary

### Run Unit Tests
```bash
# All sandbox tests
pytest tests/unit/test_sprites*.py -v

# Integration tests
pytest tests/integration/test_sprites*.py -v
```

---

## 🎯 What's Happening

### Architecture

```
You
  ↓
http://localhost:5173  (Vite Frontend - React)
  ↓
  ├─ Sandbox Chat Provider
  │   ↓
  │   http://localhost:8000/api/sandbox/*  (Backend API)
  │   ↓
  │   SpritesProvider (Sprites.dev)
  │   ↓
  │   Sprites.dev API → Creates sprite VM
  │   ↓
  │   /home/sprite/workspace (Your isolated filesystem)
  │   ↓
  │   sandbox-agent (2468 port)
  │
  └─ Companion Chat Provider
      ↓
      http://localhost:3456  (Bun server)
```

### What Each Component Does

| Component | Role | Port |
|-----------|------|------|
| Frontend (Vite) | React UI with DockView | 5173 |
| Backend (FastAPI) | Control plane, token issuer | 8000 |
| Companion (Bun) | Chat with Claude | 3456 |
| Sprites.dev | Remote sandbox VMs | - |
| Sandbox-agent | CLI agent inside sprite | 2468 |

---

## ⚙️ Configuration

### Environment Variables

```bash
# Required for Sprites
export SPRITES_TOKEN="spr_abc123..."
export SPRITES_ORG="my-org"

# Optional
export SANDBOX_PORT=2468              # Port for sandbox-agent
export ANTHROPIC_API_KEY="sk-..."     # For Claude chat
export SANDBOX_WORKSPACE="."          # For local provider
```

### Getting Credentials from Vault

```bash
# Show all available secrets
vault kv list secret/agent/

# Get Sprites credentials
vault kv get secret/agent/boringdata-agent

# Get Claude API key
vault kv get -field=api_key secret/agent/anthropic

# Get all fields
vault kv get secret/agent/boringdata-agent
```

---

## 🐛 Troubleshooting

### "Backend is not running"

Check if port 8000 is already in use:
```bash
lsof -i :8000
# Kill it if needed:
kill -9 <PID>
```

### "Frontend shows blank page"

1. Check browser console for errors
2. Wait 5 seconds and refresh (Vite is slow on first load)
3. Check backend is running: `curl http://localhost:8000/health`

### "Sprites credentials not found"

```bash
# Check if set
echo $SPRITES_TOKEN
echo $SPRITES_ORG

# Get from Vault
vault kv get secret/agent/boringdata-agent

# Set manually
export SPRITES_TOKEN="your-token"
export SPRITES_ORG="your-org"
```

### "Failed to create sprite"

Check Sprites.dev quota/account:
```bash
# View logs
curl http://localhost:8000/api/sandbox/logs

# Check metrics
curl http://localhost:8000/api/sandbox/metrics
```

### "npm: command not found"

Install Node.js:
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

---

## 📚 Next Steps

### 1. Explore the UI
- Open http://localhost:5173
- Switch between chat providers
- Try running commands in the sandbox

### 2. Run Integration Tests
```bash
./examples/start.sh --test
```

### 3. Use the API Directly
```bash
# Start a sandbox with a repo
curl -X POST http://localhost:8000/api/sandbox/start \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/example/repo",
    "branch": "main",
    "anthropic_api_key": "sk-..."
  }'
```

### 4. Customize
- Add more chat providers in `src/front/providers/`
- Modify sandbox features in `src/back/boring_ui/api/modules/sandbox/`
- Customize UI in `src/front/`

---

## 📖 Documentation

| Document | Content |
|----------|---------|
| `README.md` | Full reference guide |
| `GETTING_STARTED.md` | This file |
| `../docs/DIRECT_CONNECT_ARCHITECTURE.md` | Architecture deep-dive |
| `../docs/SANDBOX_AGENT_PLAN.md` | Sandbox design |

---

## 🆘 Need Help?

### Check Logs
```bash
# Backend logs (already visible in terminal)

# Frontend logs (browser console, F12)

# Sandbox logs
curl http://localhost:8000/api/sandbox/logs
```

### Common Commands

```bash
# Status check
curl http://localhost:8000/api/sandbox/status

# Health check
curl http://localhost:8000/api/sandbox/health

# Start fresh
curl -X POST http://localhost:8000/api/sandbox/stop
curl -X POST http://localhost:8000/api/sandbox/start

# View all metrics
curl http://localhost:8000/api/sandbox/metrics | jq .
```

### Interactive Dashboard
Open the built-in dashboard for visual testing:
```
file:///home/ubuntu/projects/boring-ui/examples/sprites_chat_demo.html
```

---

## ✅ Checklist: First Run

- [ ] Set `SPRITES_TOKEN` and `SPRITES_ORG`
- [ ] Run `./examples/start.sh`
- [ ] Open http://localhost:5173
- [ ] Try sandbox chat
- [ ] Run `./examples/start.sh --test`
- [ ] Open demo dashboard
- [ ] Explore API endpoints

Done! You're ready to build. 🚀
