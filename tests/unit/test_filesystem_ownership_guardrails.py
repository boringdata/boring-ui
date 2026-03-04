"""Filesystem/git ownership guardrails for workspace-core authority (bd-39kx)."""

from pathlib import Path

from fastapi.testclient import TestClient

from boring_ui.api.app import create_app
from boring_ui.api.config import APIConfig


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    REPO_ROOT
    / "docs"
    / "exec-plans"
    / "backlog"
    / "boring-ui-core-ownership-contract.md"
)
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "README.md"


def _route_paths() -> set[str]:
    app = create_app(
        APIConfig(workspace_root=REPO_ROOT),
        include_pty=False,
        include_stream=False,
        include_approval=False,
    )
    return {route.path for route in app.routes if hasattr(route, "path")}


def test_contract_declares_workspace_core_filesystem_authority() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "/api/v1/files/*`, `/api/v1/git/*" in text
    assert "boring-ui` workspace-core" in text
    assert "No filesystem authority in `boring-macro` or `boring-sandbox`." in text


def test_workspace_core_mounts_filesystem_and_git_families() -> None:
    paths = _route_paths()
    assert "/api/v1/files/list" in paths
    assert "/api/v1/files/read" in paths
    assert "/api/v1/files/write" in paths
    assert "/api/v1/git/status" in paths
    assert "/api/v1/git/diff" in paths
    assert "/api/v1/git/show" in paths


def test_capabilities_emit_workspace_core_contract_metadata(monkeypatch) -> None:
    monkeypatch.setenv("CAPABILITIES_INCLUDE_CONTRACT_METADATA", "1")
    app = create_app(
        APIConfig(workspace_root=REPO_ROOT),
        include_pty=False,
        include_stream=False,
        include_approval=False,
    )
    client = TestClient(app)
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    routers = {item["name"]: item for item in response.json()["routers"]}
    assert routers["files"]["contract_metadata"]["owner_service"] == "workspace-core"
    assert routers["files"]["contract_metadata"]["canonical_families"] == ["/api/v1/files/*"]
    assert routers["git"]["contract_metadata"]["owner_service"] == "workspace-core"
    assert routers["git"]["contract_metadata"]["canonical_families"] == ["/api/v1/git/*"]


def test_workspace_boundary_module_does_not_own_filesystem_business_logic() -> None:
    control_plane_root = REPO_ROOT / "src" / "back" / "boring_ui" / "api" / "modules" / "control_plane"
    forbidden_markers = (
        "modules.files",
        "modules.git",
        "create_file_router(",
        "create_git_router(",
    )

    for source in control_plane_root.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        for marker in forbidden_markers:
            assert marker not in text, f"{source}: {marker}"


def test_runbook_declares_filesystem_authority_boundary() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "/api/v1/files/*" in text
    assert "/api/v1/git/*" in text
    assert "keep workspace/user/collaboration logic in `boring-ui`" in text
