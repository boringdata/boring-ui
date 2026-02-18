"""Contract tests for bd-3g1g.5.4 (workspace-core + pty-service boundaries).

These tests intentionally assert canonical route surfaces and deny/failure
conditions that should remain stable across refactors.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from boring_ui.api import APIConfig, create_app


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# Test Project\n", encoding="utf-8")
    return tmp_path


def test_workspace_core_files_canonical_routes_and_traversal_denied(
    workspace: Path,
) -> None:
    app = create_app(APIConfig(workspace_root=workspace), include_pty=False, include_stream=False, include_approval=False)
    client = TestClient(app)

    list_resp = client.get("/api/v1/files/list", params={"path": "."})
    assert list_resp.status_code == 200
    assert "entries" in list_resp.json()

    read_resp = client.get("/api/v1/files/read", params={"path": "README.md"})
    assert read_resp.status_code == 200
    assert read_resp.json()["content"].startswith("# Test Project")

    traversal = client.get("/api/v1/files/read", params={"path": "../etc/passwd"})
    assert traversal.status_code == 400
    assert "Path traversal detected" in traversal.json()["detail"]


def test_workspace_core_git_canonical_routes_and_traversal_denied(workspace: Path) -> None:
    app = create_app(APIConfig(workspace_root=workspace), include_pty=False, include_stream=False, include_approval=False)
    client = TestClient(app)

    status_resp = client.get("/api/v1/git/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "is_repo" in data

    traversal = client.get("/api/v1/git/diff", params={"path": "../.git/config"})
    assert traversal.status_code == 400
    assert "Path traversal detected" in traversal.json()["detail"]


def test_router_selection_denies_disabled_files_or_git(workspace: Path) -> None:
    config = APIConfig(workspace_root=workspace)

    git_only = create_app(config, routers=["git"])
    files_only = create_app(config, routers=["files"])

    git_client = TestClient(git_only)
    files_client = TestClient(files_only)

    assert git_client.get("/api/v1/git/status").status_code == 200
    assert git_client.get("/api/v1/files/list", params={"path": "."}).status_code == 404

    assert files_client.get("/api/v1/files/list", params={"path": "."}).status_code == 200
    assert files_client.get("/api/v1/git/status").status_code == 404


def test_pty_router_presence_and_unknown_provider_is_denied(workspace: Path) -> None:
    config = APIConfig(workspace_root=workspace)
    app = create_app(config, include_stream=False, include_approval=False, include_pty=True)

    paths = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/ws/pty" in paths

    client = TestClient(app)
    # The server may close before or right after the handshake; accept either
    # behavior and assert the close code.
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws/pty?provider=does-not-exist") as ws:
            ws.receive_text()
    assert excinfo.value.code == 4003


def test_pty_router_absent_when_disabled(workspace: Path) -> None:
    config = APIConfig(workspace_root=workspace)
    app = create_app(config, include_stream=False, include_approval=False, include_pty=False)

    paths = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/ws/pty" not in paths
