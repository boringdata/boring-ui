"""Guardrails for boring-macro domain-only API boundary (bd-2wj7)."""

from pathlib import Path

from boring_ui.api.app import create_app
from boring_ui.api.config import APIConfig


REPO_ROOT = Path(__file__).resolve().parents[2]
OWNERSHIP_CONTRACT = (
    REPO_ROOT
    / "docs"
    / "exec-plans"
    / "backlog"
    / "boring-ui-core-ownership-contract.md"
)


def _route_paths() -> set[str]:
    app = create_app(
        APIConfig(workspace_root=REPO_ROOT),
        include_pty=False,
        include_stream=False,
        include_approval=False,
    )
    return {route.path for route in app.routes if hasattr(route, "path")}


def test_macro_boundary_contract_explicitly_limits_macro_scope() -> None:
    text = OWNERSHIP_CONTRACT.read_text(encoding="utf-8")
    assert "/api/v1/macro/*" in text
    assert "Domain extension only; not workspace authority." in text
    assert "No filesystem authority in `boring-macro` or `boring-sandbox`." in text


def test_macro_boundary_core_does_not_mount_macro_domain_routes() -> None:
    paths = _route_paths()
    assert not any(path.startswith("/api/v1/macro") for path in paths)


def test_macro_boundary_core_keeps_workspace_user_control_plane_routes() -> None:
    paths = _route_paths()
    expected_core_prefixes = (
        "/auth/",
        "/api/v1/me",
        "/api/v1/workspaces",
    )
    for prefix in expected_core_prefixes:
        assert any(path.startswith(prefix) for path in paths), prefix


def test_macro_boundary_no_backend_module_owns_macro_path_family() -> None:
    api_root = REPO_ROOT / "src" / "back" / "boring_ui" / "api"
    for source in api_root.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "/api/v1/macro" not in text, source
