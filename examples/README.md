# Sprites + Chat Examples

Complete examples showing how to run boring-ui with Sprites.dev as the sandbox provider along with the regular chat panels.

## Quick Start

### 1. Get Sprites Credentials

```bash
# From Vault
export SPRITES_TOKEN=$(vault kv get -field=api_token secret/agent/boringdata-agent)
export SPRITES_ORG=$(vault kv get -field=sprites_org secret/agent/boringdata-agent)

# Or manually
export SPRITES_TOKEN="your-sprites-token"
export SPRITES_ORG="your-org-slug"
```

### 2. Run the Full App

**Option A: Using the Python script** (recommended)

```bash
cd /home/ubuntu/projects/boring-ui

export SPRITES_TOKEN="your-token"
export SPRITES_ORG="your-org"

python3 examples/sprites_chat_example.py
```

**Option B: Manual startup**

Terminal 1 - Backend:
```bash
cd /home/ubuntu/projects/boring-ui
pip3 install -e . --break-system-packages

export SANDBOX_PROVIDER=sprites
export SPRITES_TOKEN="your-token"
export SPRITES_ORG="your-org"

python3 -c "
from boring_ui.api.app import create_app
import uvicorn

app = create_app(include_sandbox=True, include_companion=True)
uvicorn.run(app, host='0.0.0.0', port=8000)
"
```

Terminal 2 - Frontend:
```bash
cd /home/ubuntu/projects/boring-ui
npx vite --host 0.0.0.0 --port 5173
```

### 3. Open the App

- **Main UI**: http://localhost:5173
- **Sandbox Chat**: http://localhost:5173?chat=sandbox
- **Companion Chat**: http://localhost:5173?chat=companion
- **Demo Dashboard**: Open `examples/sprites_chat_demo.html` in browser

## Files

### `sprites_chat_example.py`

Automated startup script that:
- ✅ Checks all requirements (Python, Node, Sprites credentials)
- ✅ Installs dependencies
- ✅ Starts backend with Sprites provider
- ✅ Starts frontend Vite server
- ✅ Prints helpful links and commands

**Usage:**
```bash
export SPRITES_TOKEN="..."
export SPRITES_ORG="..."
python3 examples/sprites_chat_example.py
```

### `sprites_chat_demo.html`

Interactive dashboard with:
- 📦 **Sandbox Panel**: Start/stop sprites, check health, view logs, see metrics
- 💬 **Chat Panel**: Fetch capabilities, test integration
- 🔍 **API Explorer**: Make custom requests to any endpoint

**Usage:**
1. Start the app with `sprites_chat_example.py`
2. Open `examples/sprites_chat_demo.html` in browser
3. Click buttons to test various operations

## Architecture

```
┌─────────────────────────────────────────┐
│       boring-ui Frontend (React)        │
│  ┌──────────────┐      ┌──────────────┐ │
│  │ Chat Panel   │      │ Sandbox Chat │ │
│  └──────────────┘      └──────────────┘ │
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────┐
      │                     │
      ▼                     ▼
┌─────────────┐      ┌─────────────────────┐
│ Companion   │      │ Backend (FastAPI)   │
│ (Bun, 3456)│      │ ┌─────────────────┐ │
└─────────────┘      │ │ Sprites Provider│ │
                     │ │ (Sprites.dev)   │ │
                     │ └────────┬────────┘ │
                     └──────────┼──────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
            ┌──────────────────┐    ┌──────────────────┐
            │ Sprites.dev API  │    │ Sprite VM        │
            │ (REST)           │    │ /home/sprite/*   │
            └──────────────────┘    │ sandbox-agent    │
                                    └──────────────────┘
```

## API Endpoints

### Sandbox Management

```bash
# Check status
curl http://localhost:8000/api/sandbox/status

# Start sandbox (creates sprite)
curl -X POST http://localhost:8000/api/sandbox/start

# Health check
curl http://localhost:8000/api/sandbox/health

# Get logs (last N lines)
curl http://localhost:8000/api/sandbox/logs?limit=50

# Stream logs (Server-Sent Events)
curl http://localhost:8000/api/sandbox/logs/stream

# Get metrics
curl http://localhost:8000/api/sandbox/metrics

# Stop sandbox
curl -X POST http://localhost:8000/api/sandbox/stop
```

### Chat & Capabilities

```bash
# Get capabilities (both providers)
curl http://localhost:8000/api/capabilities

# Health check
curl http://localhost:8000/health
```

## Configuration

### Environment Variables

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `SPRITES_TOKEN` | ✅ | `spr_abc123...` | Sprites.dev API token |
| `SPRITES_ORG` | ✅ | `my-org` | Sprites.dev org slug |
| `SANDBOX_PROVIDER` | | `sprites` | Provider type (local/sprites/modal) |
| `SANDBOX_PORT` | | `2468` | Port for sandbox-agent |
| `ANTHROPIC_API_KEY` | | `sk-...` | For Claude chat |

### Backend Startup

The app factory uses environment variables to configure the Sprites provider:

```python
from boring_ui.api.app import create_app

app = create_app(
    include_sandbox=True,      # Enable sandbox router
    include_companion=True,    # Enable Companion server
)

# Environment variables are used automatically:
# SANDBOX_PROVIDER=sprites
# SPRITES_TOKEN=...
# SPRITES_ORG=...
```

## Testing

### Unit Tests

```bash
# Sprites provider unit tests
pytest tests/unit/test_sprites_provider.py -v

# Sprites client unit tests
pytest tests/unit/test_sprites_client.py -v
```

### Integration Tests

```bash
# Integration tests with stub server (no real Sprites needed)
pytest tests/integration/test_sprites_integration.py -v
```

### Manual Testing

1. **Via HTML dashboard**: Open `examples/sprites_chat_demo.html`
2. **Via API**: Use curl commands above
3. **Via browser**: Visit http://localhost:5173?chat=sandbox

## Troubleshooting

### "SPRITES_TOKEN not found"
```bash
# Check credentials
echo $SPRITES_TOKEN
echo $SPRITES_ORG

# Set from Vault
export SPRITES_TOKEN=$(vault kv get -field=api_token secret/agent/boringdata-agent)
export SPRITES_ORG=$(vault kv get -field=sprites_org secret/agent/boringdata-agent)
```

### "Failed to create sprite"
```bash
# Check if sprite was created
curl -s http://localhost:8000/api/sandbox/status | jq .

# View logs
curl -s http://localhost:8000/api/sandbox/logs | jq -r '.logs[]'
```

### Frontend shows blank page
```bash
# Check if backend is running
curl http://localhost:8000/api/sandbox/status

# Check browser console for errors
# Vite dev server might be slow - wait 5 seconds and refresh
```

### "npm: command not found"
```bash
# Install Node.js
# On Linux:
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

## Next Steps

- **Customize chat providers**: Edit `src/front/providers/` to add your own
- **Add sandbox features**: Modify `src/back/boring_ui/api/modules/sandbox/`
- **Test with real repos**: Pass `repo_url` and `branch` to sandbox start
- **Enable Claude API**: Set `ANTHROPIC_API_KEY` for full Claude integration

## References

- [Sprites.dev Documentation](https://sprites.dev)
- [boring-ui Architecture](../docs/DIRECT_CONNECT_ARCHITECTURE.md)
- [Sandbox Provider Design](../docs/SANDBOX_AGENT_PLAN.md)
