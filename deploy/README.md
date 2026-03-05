# Deployment

All deployment configs live in boring-ui. The sandbox data plane uses
`vendor/boring-sandbox/` (git submodule).

## Modes

| Mode | What runs | Use case |
|------|-----------|----------|
| **Core** | boring-ui backend + frontend | Standalone IDE, no sandbox |
| **Edge** | boring-ui control plane + boring-sandbox data plane + frontend | Full sandbox-backed deployment |

## Quick Reference

### Docker — Core mode

```bash
cp deploy/docker/.env.core.example .env
docker compose -f deploy/docker/docker-compose.front.yml up --build
```

Services: `backend` (FastAPI :8000), `frontend` (Vite :5173)

### Docker — Edge mode

```bash
cp deploy/docker/.env.edge.example .env
# Ensure macro bundle exists at artifacts/boring-macro-bundle.tar.gz
docker compose -f deploy/docker/docker-compose.sandbox.yml up --build
```

Services: `backend` (:18001), `sandbox` (:8081), `frontend` (:5174)

### Modal — Core mode

```bash
modal deploy deploy/modal/modal_app_front.py::core
```

Single Modal app `boring-ui-core`. Requires `boring-ui-core-secrets` Modal secret.

### Modal — Edge mode (full)

```bash
bash deploy/modal/deploy_edge_mode.sh
```

Deploys two Modal apps:
- `boring-ui-edge` — control plane (boring-ui)
- `boring-sandbox` — data plane (boring-sandbox gateway)

Use `--skip-sandbox` to deploy only the control plane.

### Modal — Sandbox only

```bash
bash deploy/modal/deploy_sandbox_mode.sh
```

Deploys only the `boring-sandbox` gateway Modal app.

### Sprite — Direct deploy

```bash
bash deploy/sprite/scripts/deploy.sh <sprite-name>
```

Builds frontend + backend wheel, uploads to a Sprite instance, creates a service.

## File Layout

```
deploy/
├── docker/
│   ├── docker-compose.front.yml      # Core mode (backend + frontend)
│   ├── docker-compose.sandbox.yml    # Edge mode (backend + sandbox + frontend)
│   ├── docker-compose.yml            # Legacy all-in-one (core + edge profiles)
│   ├── Dockerfile.backend            # boring-ui FastAPI backend
│   ├── Dockerfile.frontend           # Vite dev frontend
│   ├── nginx.sandbox-proxy.conf      # Nginx proxy for legacy edge profile
│   ├── .env.core.example             # Core env template
│   └── .env.edge.example             # Edge env template
├── modal/
│   ├── modal_app_front.py            # Core mode Modal app
│   ├── modal_app_edge.py             # Edge control plane Modal app
│   ├── modal_app_sandbox.py          # Sandbox data plane Modal app
│   ├── deploy_edge_mode.sh           # Deploy both edge apps
│   └── deploy_sandbox_mode.sh        # Deploy sandbox only
├── sandbox/
│   ├── Dockerfile.sandbox            # Sandbox container (boring-macro runtime)
│   ├── entrypoint.sh                 # Sandbox container entrypoint
│   └── scripts/
│       └── build_macro_bundle.sh     # Build macro bundle (wheel + static + bootstrap)
├── sprite/
│   └── scripts/
│       └── deploy.sh                 # Direct Sprite deploy script
└── sql/
    └── control_plane_supabase_schema.sql
```

## Submodule Setup

Edge mode requires the boring-sandbox submodule:

```bash
git submodule update --init vendor/boring-sandbox
```

The deploy scripts auto-init it if missing.

## Building the Macro Bundle

Required for Docker edge mode (`Dockerfile.sandbox` expects `artifacts/boring-macro-bundle.tar.gz`):

```bash
# Set boring-macro repo path (or it auto-discovers ../boring-macro)
export BORING_MACRO_ROOT=/path/to/boring-macro

# Optional: point to pre-built static assets
export BM_STATIC_PATH=/path/to/boring-macro/src/web/dist

# Build
bash deploy/sandbox/scripts/build_macro_bundle.sh

# Copy to expected location
cp /tmp/boring-macro-bundle.tar.gz artifacts/
```

The bundle includes: wheel, web_static assets, bootstrap.sh.

## Secrets

### Docker

Set in `.env` file (see `.env.*.example` templates).

### Modal

Create named secrets in Modal dashboard:

| Secret name | Used by | Required keys |
|---|---|---|
| `boring-ui-core-secrets` | Core + Edge control plane | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_DB_URL`, `BORING_SETTINGS_KEY`, `BORING_UI_SESSION_SECRET` |
| `boring-ui-sandbox-secrets` | Edge control plane | `BORING_SANDBOX_API_KEY`, `BORING_SANDBOX_BASE_URL` |
| `boring-sandbox-secrets` | Sandbox gateway | `BORING_SESSION_SECRET` (must match `BORING_UI_SESSION_SECRET`) |
| `boring-sandbox-macro-secrets` | Sandbox gateway | Macro runtime config |
| `boring-sandbox-sprite-secrets` | Sandbox gateway | Sprite provisioning |
| `boring-sandbox-mail-secrets` | Sandbox gateway | Mail/notification config |
| `boring-sandbox-macro-runtime-secrets` | Sandbox gateway | Runtime env for macros |

Key interop requirement: `BORING_SESSION_SECRET` (sandbox) must equal `BORING_UI_SESSION_SECRET` (control plane) for session cookie validation across the edge boundary.
