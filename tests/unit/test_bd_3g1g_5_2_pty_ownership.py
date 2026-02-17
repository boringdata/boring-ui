"""Ownership guards for bd-3g1g.5.2 dedicated PTY service boundary."""

from pathlib import Path

from boring_ui.api import APIConfig, create_app
from boring_ui.api.capabilities import create_default_registry


LEGACY_PTY_BRIDGE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "back"
    / "boring_ui"
    / "api"
    / "pty_bridge.py"
)


def test_legacy_pty_bridge_module_removed() -> None:
    assert not LEGACY_PTY_BRIDGE.exists(), (
        "Legacy PTY bridge module should be removed so PTY ownership stays in modules/pty only"
    )


def test_registry_pty_owner_is_modules_router() -> None:
    registry = create_default_registry()
    entry = registry.get("pty")
    assert entry is not None, "Expected pty router registration in default registry"

    info, factory = entry
    assert info.prefix == "/ws"
    assert factory.__module__ == "boring_ui.api.modules.pty.router"


def test_app_mounts_single_ws_pty_route_from_modules_router(tmp_path) -> None:
    app = create_app(APIConfig(workspace_root=tmp_path))
    pty_routes = [route for route in app.routes if getattr(route, "path", None) == "/ws/pty"]

    assert len(pty_routes) == 1, f"Expected exactly one /ws/pty route, found {len(pty_routes)}"
    endpoint = getattr(pty_routes[0], "endpoint", None)
    assert endpoint is not None
    assert endpoint.__module__ == "boring_ui.api.modules.pty.router"
