"""Guardrails for optional boring-sandbox edge-only pass-through mode (bd-3bnm)."""

from pathlib import Path

from boring_ui.api.app import create_app
from boring_ui.api.config import APIConfig
from boring_ui.api.modules.control_plane.workspace_boundary_router import (
    _is_allowed_workspace_passthrough_target,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    REPO_ROOT
    / "docs"
    / "exec-plans"
    / "backlog"
    / "boring-ui-core-ownership-contract.md"
)
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "README.md"


def test_sandbox_edge_contract_keeps_only_edge_in_sandbox() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "### Stays in `boring-sandbox`" in text
    assert "L7 edge routing/proxying." in text
    assert "Provisioning orchestration for runtime infrastructure." in text
    assert "Token/header injection for upstream calls." in text
    assert "### Moves to `boring-ui` core" in text


def test_sandbox_edge_passthrough_allowlist_is_controlled() -> None:
    assert _is_allowed_workspace_passthrough_target("/api/v1/me")
    assert _is_allowed_workspace_passthrough_target("/api/v1/me/settings")
    assert _is_allowed_workspace_passthrough_target("/api/v1/workspaces")
    assert _is_allowed_workspace_passthrough_target("/api/v1/workspaces/ws-1/runtime")
    assert _is_allowed_workspace_passthrough_target("/api/v1/files/list")
    assert _is_allowed_workspace_passthrough_target("/api/v1/git/status")
    assert _is_allowed_workspace_passthrough_target("/auth/session")
    assert _is_allowed_workspace_passthrough_target("/api/capabilities")
    assert not _is_allowed_workspace_passthrough_target("/api/v1/macro/query")
    assert not _is_allowed_workspace_passthrough_target("/internal/secret")
    assert not _is_allowed_workspace_passthrough_target("/w/ws-1/setup")


def test_sandbox_edge_mode_has_workspace_boundary_route() -> None:
    app = create_app(
        APIConfig(workspace_root=REPO_ROOT),
        include_pty=False,
        include_stream=False,
        include_approval=False,
    )
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/w/{workspace_id}/{path:path}" in paths


def test_sandbox_edge_runbook_mentions_proxy_mode() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "pass-through contract" in text.lower()
    assert "boring-sandbox" in text
