# Runbooks

Operational runbooks for common tasks.

## Development

### Start Local Dev Environment

```bash
# Terminal 1: Frontend dev server
npm install
npm run dev
# -> http://localhost:5173

# Terminal 2: Backend
cd src/back
pip install -e .
export ANTHROPIC_API_KEY=$(vault kv get -field=api_key secret/agent/anthropic)
python -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app()
uvicorn.run(app, host='0.0.0.0', port=8000)
"
```

### Start with All Services

```bash
# Backend with sandbox and companion support
python -c "
from boring_ui.api.app import create_app
import uvicorn
app = create_app(include_sandbox=True, include_companion=True)
uvicorn.run(app, host='0.0.0.0', port=8000)
"

# Companion service (separate terminal)
npm run companion:service

# PI service (separate terminal)
npm run pi:service
```

### Run Tests

```bash
# Frontend unit tests
npm run test:run

# Frontend unit tests (watch mode)
npm test

# Frontend E2E tests
npm run test:e2e

# Backend tests
python3 -m pytest tests/unit/ -v

# Lint
npm run lint

# Smoke gate
scripts/gates/smoke.sh
```

### Build for Production

```bash
# App build
npm run build

# Library build (for use as npm package)
npm run build:lib

# Preview production build
npm run preview
```

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key for chat sessions | (required for chat) |
| `CORS_ORIGINS` | Comma-separated allowed origins | Dev origins + `*` |
| `COMPANION_URL` | Companion service URL | None (embedded mode) |
| `PI_URL` | PI service URL | None (embedded mode) |
| `PI_MODE` | PI rendering: `embedded` or `iframe` | `embedded` |
| `WORKSPACE_PLUGINS_ENABLED` | Enable workspace plugins | `false` |
| `WORKSPACE_PLUGIN_ALLOWLIST` | Comma-separated allowed plugins | (empty = all if enabled) |
| `LOCAL_PARITY_MODE` | `http` to exercise hosted code path locally | (unset) |

### Hosted Mode (Parity Testing)

To test hosted-mode code paths locally:

```bash
export LOCAL_PARITY_MODE=http
# Frontend will rewrite /api/* to /api/v1/* as in hosted mode
```

## Troubleshooting

### Layout Corrupted / Blank Screen
Clear localStorage for the app's storage prefix:
```javascript
// In browser console
Object.keys(localStorage).filter(k => k.startsWith('boring-ui')).forEach(k => localStorage.removeItem(k))
location.reload()
```

### Capabilities Endpoint Returns Unexpected Features
Check which routers are enabled in `create_app()`. The `/api/capabilities` response reflects exactly what was mounted. Verify with:
```bash
curl http://localhost:8000/api/capabilities | python3 -m json.tool
```

### PTY WebSocket Won't Connect
1. Verify `pty` is in enabled routers
2. Check PTY providers in config: `curl http://localhost:8000/api/config`
3. Ensure the provider name in the WS query matches a configured provider

### Chat Sessions Not Working
1. Verify `ANTHROPIC_API_KEY` is set
2. Check `chat_claude_code` appears in capabilities
3. Monitor WebSocket connection at `/ws/agent/normal/stream`
