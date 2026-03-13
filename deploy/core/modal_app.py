"""Modal ASGI deployment for boring-ui (config-driven).

Deploy via bui CLI:
    bui deploy                    # resolves secrets, builds frontend, calls modal deploy

Or directly:
    modal deploy deploy/core/modal_app.py

Reads boring.app.toml via BUI_APP_TOML env var for app name, auth, etc.
Falls back to hardcoded defaults if no config found.
"""
from __future__ import annotations

import os
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# Config: read boring.app.toml if available
# ---------------------------------------------------------------------------
_cfg = {}
_toml_path = os.environ.get("BUI_APP_TOML", "boring.app.toml")
if Path(_toml_path).exists():
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            tomllib = None
    if tomllib:
        with open(_toml_path, "rb") as f:
            _cfg = tomllib.load(f)

_app_cfg = _cfg.get("app", {})
_auth_cfg = _cfg.get("auth", {})
_deploy_cfg = _cfg.get("deploy", {})
_modal_cfg = _deploy_cfg.get("modal", {})

_app_name = (
    os.environ.get("BUI_MODAL_APP_NAME")          # bui deploy injects env-aware name
    or _modal_cfg.get("app_name")
    or _app_cfg.get("id")
    or "boring-ui-core"
)
_app_id = _app_cfg.get("id", "boring-ui")
_auth_provider = _auth_cfg.get("provider", "local")
_min_containers = _modal_cfg.get("min_containers", 0)

# ---------------------------------------------------------------------------
# Modal app
# ---------------------------------------------------------------------------
app = modal.App(_app_name)


def _base_image() -> modal.Image:
    image = (
        modal.Image.debian_slim(python_version="3.12")
        .pip_install(
            "fastapi>=0.115",
            "httpx>=0.27",
            "asyncpg>=0.30",
            "PyJWT[crypto]>=2.9",
            "uvicorn>=0.30",
            "ptyprocess>=0.7",
            "websockets>=13",
        )
        .apt_install("git", "curl")
        .add_local_dir("src/back/boring_ui", "/root/src/back/boring_ui", copy=True)
    )

    # Built frontend (from bui build or npm run build)
    for static_dir in ["dist/web", "dist"]:
        if Path(static_dir).is_dir():
            image = image.add_local_dir(static_dir, "/root/dist", copy=True)
            break

    return image


image = _base_image().env(
    {
        "PYTHONPATH": "/root/src/back",
        "DEPLOY_MODE": "core",
        "CONTROL_PLANE_APP_ID": _app_id,
        "CONTROL_PLANE_PROVIDER": _auth_provider,
        "BORING_UI_STATIC_DIR": "/root/dist",
        "BORING_UI_WORKSPACE_ROOT": "/tmp/boring-ui-workspace",
    }
)

# Secrets: bui deploy injects these as env vars via Modal's from_dict.
# For manual deploys, use Modal named secrets.
_env_secrets = {}
for key in [
    "DATABASE_URL", "NEON_AUTH_BASE_URL", "NEON_AUTH_JWKS_URL",
    "BORING_UI_SESSION_SECRET", "BORING_SETTINGS_KEY",
    "ANTHROPIC_API_KEY", "GITHUB_TOKEN",
    "GIT_REPO_URL", "GIT_AUTH_TOKEN",
    "GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY",
    "GITHUB_APP_CLIENT_ID", "GITHUB_APP_CLIENT_SECRET", "GITHUB_APP_SLUG",
    "RESEND_API_KEY",
    # Supabase legacy
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET", "SUPABASE_DB_URL",
]:
    val = os.environ.get(key)
    if val:
        _env_secrets[key] = val

secrets = []
if _env_secrets:
    secrets.append(modal.Secret.from_dict(_env_secrets))
else:
    # Fallback: use Modal named secrets (manual deploy without bui)
    try:
        secrets.append(modal.Secret.from_name("boring-ui-core-secrets"))
    except Exception:
        pass
    try:
        secrets.append(modal.Secret.from_name("boring-ui-git-secrets"))
    except Exception:
        pass


@app.function(
    image=image,
    secrets=secrets,
    timeout=600,
    min_containers=_min_containers,
    memory=1024,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def web():
    """Create and return the boring-ui FastAPI application."""
    import subprocess

    workspace_root = Path(os.environ.get("BORING_UI_WORKSPACE_ROOT", "/tmp/boring-ui-workspace"))
    workspace_root.mkdir(parents=True, exist_ok=True)

    # Bootstrap workspace from git if configured
    repo_url = os.environ.get("GIT_REPO_URL")
    git_token = os.environ.get("GIT_AUTH_TOKEN")
    if repo_url and not (workspace_root / ".git").exists():
        clone_url = repo_url
        if git_token and "://" in repo_url:
            clone_url = repo_url.replace("://", f"://x-access-token:{git_token}@", 1)
        result = subprocess.run(
            ["git", "clone", "--", clone_url, str(workspace_root)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            subprocess.run(
                ["git", "remote", "set-url", "origin", repo_url],
                cwd=workspace_root, capture_output=True,
            )
            print(f"[boot] Cloned {repo_url}")
        else:
            print(f"[boot] Clone failed: {result.stderr[:200]}")
    elif repo_url and (workspace_root / ".git").exists():
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=workspace_root, capture_output=True, text=True, timeout=30, env=env,
        )

    subprocess.run(["git", "config", "--global", "user.name", "boring-ui"], capture_output=True)
    subprocess.run(["git", "config", "--global", "user.email", "bot@boringdata.io"], capture_output=True)

    from boring_ui.runtime import app as runtime_app
    return runtime_app
