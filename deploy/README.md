# Deployment

boring-ui deploys to Fly.io with a single TypeScript backend. The Python backend and multi-mode deployment variants are being replaced.

## Architecture

| Component | Technology | Description |
|-----------|-----------|-------------|
| **Backend** | Fastify (TypeScript) | API server: files, git, exec (bwrap), auth, workspaces |
| **Frontend** | Vite (React) | Built to `dist/`, served by Fastify `@fastify/static` |
| **Database** | Neon PostgreSQL | Auth (Neon Auth/Better Auth), workspace state (Drizzle ORM) |
| **Agent** | PI (browser) | Browser-side agent, calls backend API for file/git/exec |
| **Sandbox** | bubblewrap | Isolates workspace command execution |

## Configuration

Production config via `boring.app.toml`:

```toml
[workspace]
backend = "bwrap"

[agent]
runtime = "pi"
placement = "browser"

[backend]
type = "typescript"
entry = "src/server/index.ts"
port = 8000
```

Secrets managed via Vault → `[deploy.secrets]` mapping in `boring.app.toml`.

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

## Rollback rehearsal

Use the scripted Python rollback rehearsal instead of manually stitching together env vars, `uvicorn`, and the shared smoke runner:

```bash
python3 scripts/rehearse_python_rollback.py \
  --summary-out .agent-evidence/rollback/local-summary.json
```

To preview the matching hosted rollback deploy sequence:

```bash
python3 scripts/rehearse_python_rollback.py \
  --dry-run \
  --skip-sync \
  --skip-build \
  --skip-smoke \
  --print-hosted-commands \
  --hosted-url https://boring-ui-frontend-agent.fly.dev
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
