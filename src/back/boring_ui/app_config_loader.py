"""
Loads boring.app.toml and creates a configured FastAPI app.

This is the bridge between the bui CLI config and boring-ui's create_app() factory.
The bui CLI sets BUI_APP_TOML env var pointing to the config file.

Usage:
    # Direct (uvicorn)
    BUI_APP_TOML=/path/to/boring.app.toml uvicorn boring_ui.app_config_loader:app

    # Via bui CLI (sets BUI_APP_TOML automatically)
    bui dev
"""
import importlib
import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from boring_ui.api.app import create_app
from boring_ui.api.config import APIConfig


def load_app_config(toml_path: str | None = None) -> dict:
    """Load and parse boring.app.toml."""
    if toml_path is None:
        toml_path = os.environ.get("BUI_APP_TOML", "boring.app.toml")

    path = Path(toml_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "rb") as f:
        return tomllib.load(f)


def import_router(dotted_path: str):
    """Import a router from a dotted path like 'myapp.routers.foo:router'."""
    module_path, _, attr_name = dotted_path.rpartition(":")
    if not module_path:
        raise ValueError(f"Invalid router path: {dotted_path} (expected 'module:attr')")

    module = importlib.import_module(module_path)
    router = getattr(module, attr_name, None)
    if router is None:
        raise AttributeError(f"{module_path} has no attribute {attr_name!r}")

    return router


def create_app_from_toml(toml_path: str | None = None):
    """Create a FastAPI app from boring.app.toml."""
    cfg = load_app_config(toml_path)

    app_section = cfg.get("app", {})
    backend = cfg.get("backend", {})
    auth = cfg.get("auth", {})

    # Build APIConfig from TOML
    api_config = APIConfig(
        workspace_root=Path.cwd(),
        auth_app_name=app_section.get("name", "Boring UI"),
        control_plane_app_id=app_section.get("id", "boring-ui"),
    )

    # Auth provider
    provider = auth.get("provider", "local")
    if provider == "neon":
        # Neon config comes from deploy.neon section or env vars
        deploy_neon = cfg.get("deploy", {}).get("neon", {})
        if deploy_neon.get("auth_url"):
            api_config.neon_auth_base_url = deploy_neon["auth_url"]
        if deploy_neon.get("jwks_url"):
            api_config.neon_auth_jwks_url = deploy_neon["jwks_url"]
    elif provider == "none":
        api_config.control_plane_enabled = False

    # Session config
    if auth.get("session_cookie"):
        api_config.auth_session_cookie_name = auth["session_cookie"]
    if auth.get("session_ttl"):
        api_config.auth_session_ttl_seconds = auth["session_ttl"]

    # Create the base app
    fastapi_app = create_app(config=api_config)

    # Mount child app routers
    for router_path in backend.get("routers", []):
        try:
            router = import_router(router_path)
            # Determine prefix from router or default to /api/x/<name>
            module_name = router_path.split(":")[0].split(".")[-1]
            prefix = f"/api/x/{module_name}"
            fastapi_app.include_router(router, prefix=prefix)
        except Exception as e:
            print(f"[bui] warn: failed to load router {router_path}: {e}")

    return fastapi_app


def _create_app():
    """Lazy app factory — only called when uvicorn imports this module."""
    try:
        return create_app_from_toml()
    except FileNotFoundError:
        # No boring.app.toml — fall back to default boring-ui app
        return create_app(config=APIConfig(workspace_root=Path.cwd()))


# Module-level app instance for uvicorn
# uvicorn boring_ui.app_config_loader:app
app = _create_app()
