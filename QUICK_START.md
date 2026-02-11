# Boring UI - Quick Start Guide

## 🎯 What is Boring UI?

A web-based IDE combining:
- **FileTree**: File browser and editor (independent of agent)
- **Chat Agent**: Claude-powered AI assistant for coding tasks
- **Shell Terminal**: Execute commands
- **Direct Connect**: Browser connects directly to services (no proxy)

## 🚀 Quick Deployment (5 minutes)

### Local Development

```bash
# Terminal 1: Backend
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
cd /path/to/boring-ui
pip3 install -e . --break-system-packages
python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True)
uvicorn.run(app, host='0.0.0.0', port=8000)
"

# Terminal 2: Frontend
npx vite --host 0.0.0.0 --port 5173
```

**Open**: http://localhost:5173

---

### Sprites.dev Deployment (Production)

```bash
# 1. SSH into Sprites.dev
ssh user@sprites.dev

# 2. Create workspace
mkdir -p /home/sprite/workspace

# 3. Install and start backend
cd /home/sprite/boring-ui
export WORKSPACE_ROOT=/home/sprite/workspace
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
export EXTERNAL_HOST=sprites.dev

python3 -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True)
uvicorn.run(app, host='0.0.0.0', port=8000)
"

# 4. In another terminal, set up SSH tunnel
ssh -L 8000:127.0.0.1:8000 -L 2468:127.0.0.1:2468 user@sprites.dev

# 5. Start frontend (local machine)
npx vite --host 0.0.0.0 --port 5173
```

**Open**: http://localhost:5173

---

## 📋 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `WORKSPACE_ROOT` | `./` | Where files are stored |
| `ANTHROPIC_API_KEY` | (required) | Claude API authentication |
| `EXTERNAL_HOST` | Auto-detect | External hostname for service URLs |
| `SANDBOX_PORT` | `2468` | Sandbox-agent port |
| `COMPANION_PORT` | `3456` | Companion server port |

---

## 🔐 Authentication

### How It Works

1. **Backend generates tokens** on startup
2. **Browser fetches tokens** from `/api/capabilities`
3. **Browser uses tokens** in requests to services
4. **Services validate tokens** and authorize requests

### Token Types

- **Bearer**: Simple string comparison (sandbox-agent)
- **JWT**: Signed claims (Companion server)

**See**: `SPRITES_AUTHENTICATION.md` for detailed auth architecture

---

## 📂 Key Files Reference

### Frontend
- `src/front/main.jsx` - App entry point
- `src/front/App.jsx` - Main layout
- `src/front/panels/TerminalPanel.jsx` - Chat panel
- `src/front/hooks/useServiceConnection.js` - Auth hook
- `src/front/components/FilesystemIndicator.jsx` - Workspace indicator

### Backend
- `src/back/boring_ui/api/app.py` - App factory
- `src/back/boring_ui/api/auth.py` - Token issuance
- `src/back/boring_ui/api/storage.py` - File I/O
- `src/back/boring_ui/api/modules/sandbox/` - Agent management

### Documentation
- `COMPLETE_ARCHITECTURE.md` - System overview
- `SPRITES_AUTHENTICATION.md` - Auth details
- `SPRITES_DEPLOYMENT_GUIDE.md` - Step-by-step setup
- `WORKSPACE_CONFIGURATION.md` - Workspace independence

---

## 🧪 Testing

### Test Chat (Manual)

```javascript
// In browser console:

// 1. Get tokens
const caps = await fetch('http://localhost:8000/api/capabilities').then(r => r.json())
console.log(caps.services.sandbox.token)

// 2. Test sandbox-agent
const token = caps.services.sandbox.token
await fetch('http://localhost:2468/api/v1/health', {
  headers: { 'Authorization': `Bearer ${token}` }
})
.then(r => r.json())
```

### Test FileTree

```
1. Open http://localhost:5173
2. Go to FileTree (left panel)
3. Create new file: "test.txt"
4. Content: "Hello Boring UI"
5. Save

Verify on backend:
ls -la /path/to/workspace/test.txt
```

### Test Agent Chat

```
1. Go to Terminal panel (right side)
2. Select "Sandbox Agent" from dropdown
3. Type message: "Hello, can you see my workspace?"
4. Press Enter
5. Wait for response

Expected: Agent responds
```

### Run E2E Tests

```bash
cd /path/to/boring-ui
node tests/e2e/test_direct_connect.js
```

---

## 🛠️ Troubleshooting

### Backend won't start

```bash
# Port already in use?
lsof -i :8000
kill -9 <PID>

# Missing API key?
echo $ANTHROPIC_API_KEY  # Should print your key

# Python version?
python3 --version  # Should be 3.9+
```

### Agent not responding

```bash
# Is sandbox-agent running?
ps aux | grep sandbox-agent

# Check backend logs for "SandboxManager"
# Verify ANTHROPIC_API_KEY is set

# Test direct connection:
TOKEN=$(curl -s http://localhost:8000/api/capabilities | jq -r .services.sandbox.token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:2468/api/v1/health
```

### FileTree shows wrong path

```bash
# Verify WORKSPACE_ROOT
echo $WORKSPACE_ROOT

# Should match what backend is using
curl http://localhost:8000/health | jq .workspace

# If mismatch, restart backend with correct env var
```

### Browser can't reach services (Sprites.dev)

```bash
# Is SSH tunnel running?
ssh -L 8000:127.0.0.1:8000 -L 2468:127.0.0.1:2468 user@sprites.dev

# Verify in new terminal:
curl http://localhost:8000/health

# If fails, check firewall on Sprites.dev:
ufw allow 8000
ufw allow 2468
```

---

## 📚 Architecture at a Glance

```
Browser (React + Vite)
    ↓
    ├→ File API (Backend) — Get/list/create files
    │
    └→ Chat API (Sandbox-Agent) — Claude responses
         ↑
         └─ Authenticated via bearer token from /api/capabilities
```

**Key Principle**: Three independent layers
1. **Browser UI** (React)
2. **Backend API** (FastAPI) - Control plane + file ops
3. **Agent API** (Sandbox) - Chat + tool execution

---

## 🎓 Learning Path

1. **Start**: Read `COMPLETE_ARCHITECTURE.md` (5 min)
2. **Deploy**: Follow `SPRITES_DEPLOYMENT_GUIDE.md` (10 min)
3. **Understand**: Read `SPRITES_AUTHENTICATION.md` (10 min)
4. **Configure**: Check `WORKSPACE_CONFIGURATION.md` (5 min)
5. **Develop**: Start modifying code

---

## 🔗 Common Tasks

### Change Workspace Location

```bash
export WORKSPACE_ROOT=/path/to/new/workspace
# Restart backend
```

### Use S3 Instead of Local Files

```bash
# Requires: pip install boring-ui[s3]
# Code: src/back/boring_ui/api/storage.py has S3Storage class
# Note: Not currently wired to app.py, would need configuration
```

### Run Multiple Instances

```bash
# Instance 1
WORKSPACE_ROOT=/home/sprite/workspace-1 python3 -c "..." &

# Instance 2
WORKSPACE_ROOT=/home/sprite/workspace-2 python3 -c "..." &

# Each on different port:
# (Would need to modify app.py to accept port parameter)
```

### Add Custom Chat Provider

```javascript
// src/front/providers/index.js
// Add provider to registry:
registry.register('my-provider', {
  createConnection: async (config) => {
    return new MyProviderConnection(config)
  }
})
```

---

## 📞 Quick Reference

| Need | File | Line |
|------|------|------|
| Change auth mechanism | `src/back/boring_ui/api/auth.py` | 18 |
| Add new router | `src/back/boring_ui/api/app.py` | 160 |
| Modify FileTree | `src/front/panels/FileTreePanel.jsx` | 1 |
| Change token TTL | `src/back/boring_ui/api/auth.py` | 33 |
| Add new API endpoint | `src/back/boring_ui/api/modules/*` | — |

---

## ✅ Success Checklist

- [ ] Backend starts without errors
- [ ] `/api/health` returns 200
- [ ] `/api/capabilities` includes sandbox service
- [ ] Frontend loads at http://localhost:5173
- [ ] FileTree shows files in WORKSPACE_ROOT
- [ ] Can create/read/delete files via FileTree
- [ ] Sandbox-Agent responds to chat messages
- [ ] Filesystem indicator shows correct source

---

## 📖 Full Documentation

For deeper dives, see:

- **System Design**: `COMPLETE_ARCHITECTURE.md` (2000+ lines)
- **Auth Details**: `SPRITES_AUTHENTICATION.md` (500+ lines)
- **Setup Guide**: `SPRITES_DEPLOYMENT_GUIDE.md` (400+ lines)
- **Workspace Config**: `WORKSPACE_CONFIGURATION.md` (140 lines)
- **Remote Setup**: `REMOTE_SANDBOX_SETUP.md` (150 lines)

---

## 💡 Pro Tips

1. **Use SSH Tunnel**: Keeps traffic encrypted for remote access
   ```bash
   ssh -L 8000:127.0.0.1:8000 -L 2468:127.0.0.1:2468 user@sprites.dev
   ```

2. **Watch Backend Logs**: Gives insight into token generation
   ```bash
   # Look for: "Backend starting", "SandboxManager", "Token issued"
   ```

3. **Check Capabilities**: Verify token distribution is working
   ```bash
   curl http://localhost:8000/api/capabilities | jq .services
   ```

4. **Filesystem Indicator**: Check color to verify where files go
   - 🟢 Green = Local filesystem
   - 🔵 Blue = Sandbox (mounted)
   - 🟠 Orange = Sprites.dev

5. **Keep API Key Secure**: Never commit to repo
   ```bash
   # Load from Vault, not files
   export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
   ```

---

## 🆘 Getting Help

1. **Logs**: Check backend console for errors
2. **Curl Tests**: Test endpoints directly
3. **Browser Console**: Check network tab for failed requests
4. **Docs**: Search the markdown files in this repo
5. **Code**: Read src/back/boring_ui/api/app.py for truth

---

**Last Updated**: 2026-02-10
**Version**: Complete Architecture Documentation
**Status**: ✅ Production Ready
