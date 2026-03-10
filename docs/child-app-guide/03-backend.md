# 3. Backend Integration

[< Back to Index](README.md) | [Prev: Scaffolding](02-scaffolding.md) | [Next: Frontend >](04-frontend.md)

---

## 3.1 The App Factory (`backend/app.py`)

This is the heart of integration. Your app wraps boring-ui's `create_app()` and adds domain-specific routers.

```python
"""My app backend — boring-ui instance with custom domain router."""

import json
import os
from pathlib import Path

from boring_ui.api import APIConfig, create_app as _create_app
from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import JSONResponse

# Load .env from src/web/ directory (where the frontend code lives)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from .config import get_config
from .modules.my_domain.router import create_my_domain_router


def create_app():
    """Create the app using boring-ui's factory."""
    cfg = get_config()

    # Configure boring-ui
    bui_config = APIConfig(
        workspace_root=cfg.workspace_root,
        cors_origins=["*"],
        # Register app-specific API prefixes so workspace boundary
        # router forwards them instead of serving the SPA fallback.
        extra_passthrough_roots=(
            "/api/v1/my-domain",
        ),
    )

    # Create base app — toggle modules you need
    app = _create_app(
        config=bui_config,
        include_stream=False,   # No Claude chat (use companion instead)
        include_pty=True,       # Terminal access
        include_approval=False, # Tool approval workflow
    )

    # Mount your domain router
    domain_router = create_my_domain_router(cfg)
    app.include_router(domain_router, prefix="/api/v1/my-domain")

    # Patch /api/capabilities to advertise your features.
    # Middleware is needed because create_app() registers the capabilities
    # endpoint internally — you can't just override it.
    @app.middleware("http")
    async def patch_capabilities(request: Request, call_next):
        response = await call_next(request)
        if request.url.path == "/api/capabilities" and response.status_code == 200:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()
            data = json.loads(body)
            data.setdefault("features", {})["my_domain"] = True
            return JSONResponse(content=data)
        return response

    return app


# Module-level app for uvicorn:
#   Dev:  python -m uvicorn backend.app:app --reload
#   Prod: backend.runtime imports this and adds static file serving
app = create_app()
```

**Why two `app` objects?** `backend.app:app` is used during development (no static files). `backend.runtime:app` wraps the same app but adds `mount_static()` for production deployments where the frontend is pre-built.

## 3.2 Configuration (`backend/config.py`)

Resolve all app-specific config from environment variables.

```python
"""App configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    workspace_root: Path
    database_url: str | None = None
    # Add your domain-specific config fields


def env_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def normalize_deploy_env() -> None:
    """Normalize env var aliases from Modal secrets.

    Maps alternative names to canonical names. Safe to call multiple times.
    Called by modal_app.py BEFORE importing runtime.
    """
    # Neon / generic Postgres aliases
    # DATABASE_URL is the canonical env var for Neon. boring-ui reads it directly.

    # Supabase aliases (legacy — if using supabase control plane)
    if not os.environ.get("SUPABASE_URL"):
        v = (os.environ.get("SUPABASE_PROJECT_URL") or "").strip()
        if v:
            os.environ["SUPABASE_URL"] = v
    if not os.environ.get("SUPABASE_ANON_KEY"):
        v = (os.environ.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
        if v:
            os.environ["SUPABASE_ANON_KEY"] = v

    # DB pooler override (Supabase legacy)
    pooler = (os.environ.get("SUPABASE_DB_URL_POOLER") or "").strip()
    if pooler:
        os.environ["SUPABASE_DB_URL"] = pooler
    elif not os.environ.get("SUPABASE_DB_URL"):
        for key in ("SUPABASE_DATABASE_URL", "SUPABASE_POSTGRES_URL"):
            v = (os.environ.get(key) or "").strip()
            if v:
                os.environ["SUPABASE_DB_URL"] = v
                break

    # Your domain-specific aliases
    # if not os.environ.get("MY_APP_DB_URL"):
    #     v = (os.environ.get("DATABASE_URL") or "").strip()
    #     if v:
    #         os.environ["MY_APP_DB_URL"] = v


def get_config() -> AppConfig:
    """Build config from environment."""
    configured_root = (os.environ.get("MY_APP_WORKSPACE_ROOT") or "").strip()
    if configured_root:
        root = Path(configured_root).expanduser().resolve()
    else:
        candidate = Path(__file__).resolve().parents[3]  # src/web/backend -> root
        if (candidate / "src" / "web").is_dir():
            root = candidate
        else:
            root = Path.cwd().resolve()

    database_url = (os.environ.get("MY_APP_DATABASE_URL") or "").strip() or None

    return AppConfig(
        workspace_root=root,
        database_url=database_url,
    )
```

## 3.3 Production Runtime (`backend/runtime.py`)

Serves the built frontend alongside the API in production.

```python
"""Production ASGI wrapper — API + static frontend."""

from __future__ import annotations

import os
from pathlib import Path

from boring_ui.runtime import mount_static

from .app import create_app

app = create_app()


def _resolve_static_dir() -> Path | None:
    """Find built frontend assets."""
    # 1. Explicit env var
    explicit = (os.environ.get("MY_APP_STATIC_DIR") or "").strip()
    if explicit:
        path = Path(explicit)
        if path.is_dir():
            return path

    # 2. Source checkout fallback
    source_dist = Path(__file__).resolve().parents[1] / "dist"
    if source_dist.is_dir():
        return source_dist

    return None


static_path = _resolve_static_dir()
if static_path:
    mount_static(app, static_path)
```

## 3.4 Domain Router (`backend/modules/my_domain/router.py`)

```python
"""Domain-specific API endpoints."""

from fastapi import APIRouter


def create_my_domain_router(config) -> APIRouter:
    router = APIRouter(tags=["my_domain"])

    @router.get("/items")
    async def list_items(limit: int = 50, offset: int = 0):
        # Your domain logic here
        return {"results": [], "total": 0}

    @router.get("/items/{item_id}")
    async def get_item(item_id: str):
        return {"item_id": item_id}

    return router
```

## 3.5 `create_app()` Parameters Reference

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `config` | `APIConfig()` | Central config (workspace root, CORS, PTY, auth) |
| `storage` | `LocalStorage` | File storage backend |
| `approval_store` | `InMemoryApprovalStore` | Approval workflow backend |
| `include_pty` | `True` | Enable terminal sessions (`/ws/pty`) |
| `include_stream` | `True` | Enable Claude Code CLI streaming (`/ws/agent/normal/stream`) |
| `include_approval` | `True` | Enable tool approval (`/api/approval`) |
| `routers` | `None` (all) | Explicit list of router names to mount |
| `registry` | default | Custom `RouterRegistry` |

**When to use `include_stream`:**
- `True` — enables native Claude Code CLI streaming (for apps that embed Claude Code directly)
- `False` — use this when your app uses the companion pattern instead (separate sidecar process), or has no AI agent at all

## 3.6 `APIConfig` Key Fields

`APIConfig` (source: `boring_ui/api/config.py`) has many fields. The most commonly set ones:

| Field | Default | Purpose |
|-------|---------|---------|
| `workspace_root` | cwd | Root directory for file operations |
| `cors_origins` | `["http://localhost:5173", ...]` | CORS allowed origins. Pass `["*"]` to allow all |
| `control_plane_enabled` | from env | Enable auth/workspace/collab module |
| `control_plane_provider` | from env | Auth provider: `local`, `neon`, or `supabase` |
| `database_url` | from env | Canonical Postgres URL (Neon or any Postgres) |
| `neon_auth_base_url` | from env | Neon Auth endpoint (required for `neon` provider) |
| `neon_auth_jwks_url` | from env | JWKS URL for Neon JWT verification |
| `auth_session_cookie_name` | `boring_session` | Session cookie name (auto-suffixed with app_id if set) |
| `auth_session_secret` | random | Secret for signing session JWTs. **Set explicitly in production** or sessions won't survive restarts |
| `auth_session_ttl_seconds` | `86400` | Session duration (24h) |
| `auth_session_secure_cookie` | `False` | Set `True` for HTTPS-only cookies |
| `auth_app_name` | `Boring UI` | App name on auth pages |
| `workspace_plugins_enabled` | `False` | Enable `{workspace}/kurt/api/` plugin system |
| `pty_providers` | `{'shell': ['bash']}` | PTY provider commands |
| `extra_passthrough_roots` | `()` | App-specific API prefixes for workspace boundary (see below) |

All fields are resolved from env vars by the `APIConfig()` constructor. See the source file for the complete list.

### Workspace Boundary Passthrough

When the control plane is enabled, all requests under `/w/{workspace_id}/` go through the workspace boundary router. This router only forwards requests whose path matches a known allow-list of API prefixes (e.g. `/api/v1/files`, `/api/v1/agent`, etc.).

**If your child app mounts custom routers** (e.g. `/api/v1/my-domain`), those paths are **not** in the built-in allow-list. Without registration, requests from the browser to `/w/{workspace_id}/api/v1/my-domain/...` will receive the SPA `index.html` instead of your API response — causing silent JSON parse failures in frontend code.

Set `extra_passthrough_roots` to register your prefixes:

```python
bui_config = APIConfig(
    workspace_root=cfg.workspace_root,
    extra_passthrough_roots=(
        "/api/v1/my-domain",
        "/api/v1/chat",   # if using chat auth routes
    ),
)
```

This applies to both the local and Supabase workspace boundary routers.

## 3.7 Companion / Agent Integration (Optional)

If your app needs an AI agent (Claude companion), add companion proxy logic. See boring-macro's `app.py` for the full pattern:

1. Probe companion upstream URL
2. Auto-start managed sidecar if configured
3. Forward HTTP requests: `POST /api/v1/agent/companion/*`
4. Bridge WebSocket: `/ws/agent/companion/{kind}/{session_id}`

Key env vars:
```bash
BM_CHAT_PROVIDER=companion         # or "none" to disable
BM_COMPANION_AUTOSTART=true        # Auto-start sidecar
BM_COMPANION_COMMAND="bunx the-companion@0.46.0 serve"
BM_COMPANION_HOST=127.0.0.1
BM_COMPANION_PORT=3456
COMPANION_URL=http://127.0.0.1:3456  # Explicit upstream URL
```
