"""Tests for `/w/{workspace_id}/...` workspace boundary precedence and proxying."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from boring_ui.api import APIConfig, create_app
import boring_ui.api.modules.control_plane.workspace_boundary_router as boundary_router_module


def _client(tmp_path: Path) -> TestClient:
    config = APIConfig(
        workspace_root=tmp_path,
        auth_dev_login_enabled=True,
        auth_dev_auto_login=False,
        control_plane_provider="local",
        database_url=None,
        neon_auth_base_url=None,
        neon_auth_jwks_url=None,
    )
    app = create_app(config=config, include_pty=False, include_stream=False, include_approval=False)
    return TestClient(app)


def _login(client: TestClient, *, user_id: str, email: str) -> None:
    response = client.get(
        f"/auth/login?user_id={user_id}&email={email}&redirect_uri=/",
        follow_redirects=False,
    )
    assert response.status_code == 302


def _create_workspace(client: TestClient, *, name: str = "Boundary") -> str:
    response = client.post("/api/v1/workspaces", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _bootstrap_owner_membership(client: TestClient, workspace_id: str) -> None:
    response = client.get(f"/api/v1/workspaces/{workspace_id}/members")
    assert response.status_code == 200


def test_workspace_scoped_boundary_routes_are_mounted(tmp_path: Path) -> None:
    client = _client(tmp_path)
    paths = [route.path for route in client.app.routes if hasattr(route, "path")]
    assert "/w/{workspace_id}/setup" in paths
    assert "/w/{workspace_id}/runtime" in paths
    assert "/w/{workspace_id}/runtime/retry" in paths
    assert "/w/{workspace_id}/settings" in paths
    assert "/w/{workspace_id}/{path:path}" in paths


def test_workspace_scoped_proxy_requires_session(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/w/ws-1/api/v1/me")
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REQUIRED"


def test_workspace_scoped_proxy_requires_membership(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client, user_id="owner-1", email="owner@example.com")
    workspace_id = _create_workspace(client)
    _bootstrap_owner_membership(client, workspace_id)

    _login(client, user_id="outsider-1", email="outsider@example.com")
    denied = client.get(f"/w/{workspace_id}/api/v1/me")
    assert denied.status_code == 403
    assert denied.json()["code"] == "WORKSPACE_MEMBERSHIP_REQUIRED"


def test_workspace_scoped_proxy_forwards_allowed_internal_paths(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client, user_id="owner-2", email="owner2@example.com")
    workspace_id = _create_workspace(client)
    _bootstrap_owner_membership(client, workspace_id)

    forwarded = client.get(f"/w/{workspace_id}/api/v1/me")
    assert forwarded.status_code == 200
    assert forwarded.json()["email"] == "owner2@example.com"


def test_workspace_scoped_proxy_forwards_filesystem_families(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client, user_id="owner-fs", email="owner-fs@example.com")
    workspace_id = _create_workspace(client)
    _bootstrap_owner_membership(client, workspace_id)

    listed = client.get(f"/w/{workspace_id}/api/v1/files/list?path=.")
    assert listed.status_code == 200
    assert "entries" in listed.json()

    git_status = client.get(f"/w/{workspace_id}/api/v1/git/status")
    assert git_status.status_code == 200


def test_workspace_scoped_root_route_allows_membership_verified_access(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client, user_id="owner-root", email="owner-root@example.com")
    workspace_id = _create_workspace(client)
    _bootstrap_owner_membership(client, workspace_id)

    response = client.get(f"/w/{workspace_id}/")
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "workspace_id": workspace_id,
        "route": "root",
    }


def test_workspace_scoped_agent_ws_allows_membership_verified_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, str] = {}

    async def fake_handle_stream_websocket(websocket, cmd="claude", base_args=None, cwd=None):
        captured["cwd"] = cwd
        await websocket.accept()
        await websocket.close()

    monkeypatch.setattr(boundary_router_module, "handle_stream_websocket", fake_handle_stream_websocket)

    client = _client(tmp_path)
    _login(client, user_id="owner-ws", email="owner-ws@example.com")
    workspace_id = _create_workspace(client, name="WS Agent")
    _bootstrap_owner_membership(client, workspace_id)

    with client.websocket_connect(f"/w/{workspace_id}/ws/agent/normal/stream") as websocket:
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_text()

    assert captured["cwd"] == str((tmp_path / workspace_id).resolve())


def test_workspace_scoped_agent_ws_requires_membership(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client, user_id="owner-ws-deny", email="owner-ws-deny@example.com")
    workspace_id = _create_workspace(client, name="WS Agent Deny")
    _bootstrap_owner_membership(client, workspace_id)

    _login(client, user_id="outsider-ws", email="outsider-ws@example.com")

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/w/{workspace_id}/ws/agent/normal/stream"):
            pass

    assert excinfo.value.code == 4403
    assert excinfo.value.reason == "WORKSPACE_MEMBERSHIP_REQUIRED"


def test_workspace_scoped_pty_ws_allows_membership_verified_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, str] = {}

    async def fake_handle_pty_websocket(websocket, config):
        captured["workspace_id"] = websocket.path_params["workspace_id"]
        await websocket.accept()
        await websocket.close()

    monkeypatch.setattr(boundary_router_module, "handle_pty_websocket", fake_handle_pty_websocket)

    client = _client(tmp_path)
    _login(client, user_id="owner-pty", email="owner-pty@example.com")
    workspace_id = _create_workspace(client, name="WS PTY")
    _bootstrap_owner_membership(client, workspace_id)

    with client.websocket_connect(f"/w/{workspace_id}/ws/pty?provider=shell") as websocket:
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_text()

    assert captured["workspace_id"] == workspace_id


def test_workspace_scoped_precedence_prefers_reserved_settings_route(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client, user_id="owner-3", email="owner3@example.com")
    workspace_id = _create_workspace(client)
    _bootstrap_owner_membership(client, workspace_id)

    updated = client.put(f"/w/{workspace_id}/settings", json={"theme": "dark"})
    assert updated.status_code == 200
    assert updated.json()["settings"]["theme"] == "dark"

    loaded = client.get(f"/w/{workspace_id}/settings")
    assert loaded.status_code == 200
    assert loaded.json()["settings"]["theme"] == "dark"


def test_workspace_scoped_proxy_denies_non_allowed_paths(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client, user_id="owner-4", email="owner4@example.com")
    workspace_id = _create_workspace(client)
    _bootstrap_owner_membership(client, workspace_id)

    denied = client.get(f"/w/{workspace_id}/internal/secret")
    assert denied.status_code == 404
    assert denied.json()["code"] == "WORKSPACE_PATH_DENIED"


def test_workspace_scoped_proxy_denies_macro_family(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client, user_id="owner-5", email="owner5@example.com")
    workspace_id = _create_workspace(client)
    _bootstrap_owner_membership(client, workspace_id)

    denied = client.get(f"/w/{workspace_id}/api/v1/macro/query")
    assert denied.status_code == 404
    assert denied.json()["code"] == "WORKSPACE_PATH_DENIED"
