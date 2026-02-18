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
    app = create_app(
        APIConfig(workspace_root=workspace),
        include_pty=False,
        include_stream=False,
        include_approval=False,
    )
    client = TestClient(app)

    list_resp = client.get("/api/v1/files/list", params={"path": "."})
    assert list_resp.status_code == 200
    assert "entries" in list_resp.json()

    read_resp = client.get("/api/v1/files/read", params={"path": "README.md"})
    assert read_resp.status_code == 200
    assert read_resp.json()["content"].startswith("# Test Project")

    traversal = client.get("/api/v1/files/read", params={"path": "../etc/passwd"})
    assert traversal.status_code == 400
    # FileService pins traversal to 400; keep message assertion broad.
    detail = traversal.json().get("detail")
    assert isinstance(detail, str)
    assert "traversal" in detail.lower()

    traversal_abs = client.get("/api/v1/files/read", params={"path": "/etc/passwd"})
    assert traversal_abs.status_code == 400
    detail_abs = traversal_abs.json().get("detail")
    assert isinstance(detail_abs, str)
    assert "traversal" in detail_abs.lower()


def test_workspace_core_git_canonical_routes_and_traversal_denied(workspace: Path) -> None:
    app = create_app(
        APIConfig(workspace_root=workspace),
        include_pty=False,
        include_stream=False,
        include_approval=False,
    )
    client = TestClient(app)

    status_resp = client.get("/api/v1/git/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "is_repo" in data
    # In a non-git workspace, canonical status endpoint still responds with is_repo=False.
    assert data["is_repo"] is False

    traversal = client.get("/api/v1/git/diff", params={"path": "../.git/config"})
    assert traversal.status_code == 400
    detail = traversal.json().get("detail")
    assert isinstance(detail, str)
    assert "traversal" in detail.lower()

    traversal_abs = client.get("/api/v1/git/diff", params={"path": "/etc/passwd"})
    assert traversal_abs.status_code == 400
    detail_abs = traversal_abs.json().get("detail")
    assert isinstance(detail_abs, str)
    assert "traversal" in detail_abs.lower()


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

    assert any(getattr(r, "path", None) == "/ws/pty" for r in app.routes)

    client = TestClient(app)
    # The server may close before or right after the handshake; accept either
    # behavior. Router currently pins unknown provider to close code 4003, but
    # some stacks may surface handshake-level failures instead.
    try:
        with client.websocket_connect("/ws/pty?provider=does-not-exist") as ws:
            ws.receive_text()
    except WebSocketDisconnect as exc:
        assert exc.code == 4003
    except Exception as exc:  # pragma: no cover
        assert "websocket" in str(exc).lower() or "provider" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("Expected unknown PTY provider to be denied")


def test_pty_router_absent_when_disabled(workspace: Path) -> None:
    config = APIConfig(workspace_root=workspace)
    app = create_app(config, include_stream=False, include_approval=False, include_pty=False)

    assert not any(getattr(r, "path", None) == "/ws/pty" for r in app.routes)
