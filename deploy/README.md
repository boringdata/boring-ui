# Deployment

boring-ui deploys to Fly.io in three agent modes. Legacy Modal, Docker Compose, Go backend, and edge-mode artifacts have been removed.

## Agent modes

| Mode | Fly app | Config | Dockerfile | Agent execution |
|------|---------|--------|------------|-----------------|
| **agent-lite** | `boring-ui-lite` | `deploy/fly-lite/fly.toml` | `deploy/fly-lite/Dockerfile` | Browser PI only, bubblewrap sandbox, no Node.js runtime sidecar |
| **agent-frontend** | `boring-ui-frontend-agent` | `deploy/fly/fly.frontend-agent.toml` | `deploy/shared/Dockerfile.backend` | Browser PI, Vite static served from backend |
| **agent-backend** | `boring-ui-backend-agent` | `deploy/fly/fly.backend-agent.toml` | `deploy/shared/Dockerfile.backend` | Server-side agent with Node.js pi_service sidecar |

All three share:
- Neon Auth (email/password)
- `data.backend = "http"` (real filesystem, not browser IndexedDB)
- Same Vault secrets via `deploy/fly/fly.secrets.sh`

### Key differences

- **agent-lite**: Minimal footprint. Browser-only PI agent, bubblewrap sandbox for exec. No Node.js at runtime. Good for lightweight single-user setups.
- **agent-frontend**: Browser PI agent with full backend (FastAPI + Vite static). No server-side agent process. Standard deploy strategy.
- **agent-backend**: Full stack with Node.js pi_service sidecar for server-side agent execution. Uses `immediate` deploy strategy to avoid stale asset mismatches during rollout.

## Deploy flow

```bash
# 1. Set secrets (requires Vault + flyctl auth)
bash deploy/fly/fly.secrets.sh <app-name>

# 2. Deploy
fly deploy -c <config-path> --remote-only

# Examples:
bash deploy/fly/fly.secrets.sh boring-ui-lite
fly deploy -c deploy/fly-lite/fly.toml --remote-only

bash deploy/fly/fly.secrets.sh boring-ui-frontend-agent
fly deploy -c deploy/fly/fly.frontend-agent.toml --remote-only

bash deploy/fly/fly.secrets.sh boring-ui-backend-agent
fly deploy -c deploy/fly/fly.backend-agent.toml --remote-only
```

## Smoke tests

```bash
# Health-only (no auth needed)
python tests/smoke/run_all.py --base-url https://<app>.fly.dev --suites health,capabilities

# Full suite with Neon auth
python tests/smoke/run_all.py \
  --base-url https://<app>.fly.dev \
  --auth-mode neon \
  --skip-signup --email <email> --password <pw>

# Include backend-agent WebSocket verification
python tests/smoke/run_all.py \
  --base-url https://boring-ui-backend-agent.fly.dev \
  --include-agent-ws ...
```

## Dockerfiles

- `deploy/shared/Dockerfile.backend` — Two-stage build (Vite frontend + Python/Node backend). Used by agent-frontend and agent-backend.
- `deploy/fly-lite/Dockerfile` — Two-stage build (Vite frontend + Python backend with bubblewrap). Used by agent-lite.
- `deploy/shared/Dockerfile.frontend` — Frontend dev image (local usage only).

## App config

Each mode has its own `boring.app.toml`:
- `deploy/shared/boring.app.toml` — agent-frontend and agent-backend
- `deploy/fly-lite/boring.app.toml` — agent-lite
- Root `boring.app.toml` — local dev (uses `lightningfs` instead of `http`)
