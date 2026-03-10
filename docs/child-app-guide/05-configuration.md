# 5. Configuration System

[< Back to Index](README.md) | [Prev: Frontend](04-frontend.md) | [Next: Deployment >](06-deployment.md)

---

## 5.1 How Config Flows

```
Environment Variables
    │
    ▼
backend/config.py (normalize_deploy_env + get_config)
    │
    ▼
boring_ui.api.APIConfig (passed to create_app)
    │
    ▼
/api/capabilities (runtime feature discovery)
    │
    ▼
Frontend useCapabilities() hook → CapabilityGate → panels render
```

## 5.2 Key boring-ui Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `CONTROL_PLANE_ENABLED` | Enable auth/workspace/collab | `true` |
| `CONTROL_PLANE_PROVIDER` | `local`, `neon`, or `supabase` | `local` |
| `CONTROL_PLANE_APP_ID` | App identifier for control plane | — |
| `CORS_ORIGINS` | Comma-separated allowed origins | `*` |
| `DATABASE_URL` | Canonical Postgres URL (Neon or any Postgres) | — |
| `NEON_AUTH_BASE_URL` | Neon Auth endpoint base URL | — |
| `NEON_AUTH_JWKS_URL` | Neon Auth JWKS endpoint for JWT verification | — |
| `SUPABASE_URL` | Supabase project URL (legacy) | — |
| `SUPABASE_ANON_KEY` | Supabase public key (legacy) | — |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase admin key (legacy) | — |
| `SUPABASE_DB_URL` | Supabase Postgres URL (fallback if `DATABASE_URL` unset) | — |
| `AUTH_APP_NAME` | App name shown on auth pages | `Boring UI` |
| `AUTH_APP_DESCRIPTION` | Tagline on auth pages | — |
| `BM_WORKSPACE_ROOT` | Workspace directory | project root or cwd |

### Auth Provider Selection

The `CONTROL_PLANE_PROVIDER` determines which auth mechanism is used:

| Provider | Auth Mechanism | Database | When to use |
|----------|----------------|----------|-------------|
| `local` | Dev bypass (no real auth) | In-memory JSON | Local development |
| `neon` | Neon Auth (Better Auth, email/password) | Neon Postgres (asyncpg) | **Production (recommended)** |
| `supabase` | Supabase GoTrue | Supabase Postgres (asyncpg) | Legacy deployments |

**Auto-detection:** If `CONTROL_PLANE_PROVIDER` is unset/`local` but `NEON_AUTH_BASE_URL` is present, Neon is auto-enabled. Similarly, if Supabase env vars are present, Supabase is auto-enabled. Neon takes priority.

## 5.3 Capabilities-Driven UI

The `/api/capabilities` endpoint is the single source of truth for what the frontend can do. Your app patches it to include domain-specific features:

```python
# In your app.py middleware
data["features"]["my_domain"] = True
```

Frontend panels declare requirements:
```javascript
registerPane({
  id: 'my-panel',
  requiresFeatures: ['my_domain'],  // Won't render if my_domain is false
})
```

When requirements are unmet, the `CapabilityGate` wrapper shows a clear error state instead of crashing.

## 5.4 `normalize_deploy_env()` Pattern

Modal secrets inject env vars with names that may differ from what boring-ui expects. The `normalize_deploy_env()` function bridges this gap:

```python
# Called by modal_app.py BEFORE importing runtime
from backend.config import normalize_deploy_env
normalize_deploy_env()

# Now env vars are canonical — safe to import runtime
from backend.runtime import app
```

This must happen before `create_app()` runs because config is read at import time.

## 5.5 Auth Session Details

boring-ui uses HS256-signed JWTs stored as HTTP-only cookies.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AUTH_SESSION_COOKIE_NAME` | `boring_session` | Cookie name. When `CONTROL_PLANE_APP_ID` is set, the cookie is auto-suffixed (e.g., `boring_session_my-app`) |
| `BORING_UI_SESSION_SECRET` | random | Secret for signing JWTs. **Must be set explicitly in production** — without it, an ephemeral random secret is generated and sessions won't survive restarts |
| `AUTH_SESSION_TTL_SECONDS` | `86400` | Session duration (24 hours) |
| `AUTH_SESSION_SECURE_COOKIE` | `false` | Set `true` for HTTPS-only cookies in production |

Source: `boring_ui/api/modules/control_plane/auth_session.py`

## 5.6 Dev vs Production Config

| Concern | Dev (`npm run dev:full`) | Production (Modal) |
|---------|------------------------|-------------------|
| Static files | Vite dev server (HMR) | `mount_static()` serves built assets |
| API proxy | Vite proxy → localhost:8000 | Same process (FastAPI) |
| Auth | `BM_DEV_AUTO_SESSION=true` | Neon Auth or Supabase control plane |
| PYTHONPATH | Set in `npm run backend` script | Set in Modal image env |

## 5.7 Startup Sequence (`npm run dev:full`)

Understanding the full boot sequence helps debug issues:

1. `concurrently` starts **backend** (uvicorn on :8000) and **frontend** (Vite on :5173) in parallel
2. Backend: loads `.env` via `python-dotenv`, calls `create_app()`, mounts routers, starts serving
3. Frontend: Vite starts with HMR, proxy rules forward `/api`, `/auth`, `/ws` to the backend
4. Browser loads `index.html` → `main.jsx` bootstraps React
5. boring-ui's `App` component fetches `GET /api/capabilities` and `GET /api/config`
6. Panels render based on capabilities: panes whose `requiresFeatures`/`requiresRouters` are unmet show error state via `CapabilityGate`

## Source Files Reference

| Concern | File |
|---------|------|
| `APIConfig` fields | `boring_ui/api/config.py` |
| `create_app()` factory | `boring_ui/api/app.py` |
| Router registry | `boring_ui/api/capabilities.py` |
| Session cookies | `boring_ui/api/modules/control_plane/auth_session.py` |
| Static serving | `boring_ui/runtime.py` |
| Workspace plugins | `boring_ui/api/workspace_plugins.py` |
