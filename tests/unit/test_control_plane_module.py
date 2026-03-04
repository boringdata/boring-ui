"""Tests for control-plane foundation module wiring and persistence."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from boring_ui.api import APIConfig, create_app
from boring_ui.api.modules.control_plane.repository import LocalControlPlaneRepository


def _scope_headers(scopes: list[str]) -> dict[str, str]:
    payload = {
        "request_id": "req-control-plane",
        "workspace_id": "workspace-1",
        "actor": {"user_id": "u-test", "service": "agent-normal", "role": "runtime"},
        "capability_claims": scopes,
        "cwd_or_worktree": ".",
    }
    return {"X-Scope-Context": json.dumps(payload)}


def test_control_plane_repository_persists_workspace_user_membership_invite_runtime(tmp_path: Path) -> None:
    state_path = tmp_path / ".boring" / "control-plane" / "state.json"
    repo = LocalControlPlaneRepository(state_path)

    user = repo.upsert_user("user-1", {"email": "owner@example.com", "display_name": "Owner"})
    repo.upsert_workspace("workspace-1", {"name": "Primary", "created_by": "user-1"})
    repo.upsert_membership(
        "membership-1",
        {
            "workspace_id": "workspace-1",
            "user_id": "user-1",
            "role": "owner",
        },
    )
    repo.upsert_invite(
        "invite-1",
        {
            "workspace_id": "workspace-1",
            "email": "editor@example.com",
            "role": "editor",
            "expires_at": "2026-03-11T00:00:00Z",
        },
    )
    repo.set_workspace_settings("workspace-1", {"timezone": "UTC", "theme": "light"})
    repo.set_workspace_runtime("workspace-1", {"state": "ready", "sprite_url": "https://sprite.local"})
    repo.upsert_user("user-1", {"display_name": "Owner Updated", "created_at": "1970-01-01T00:00:00Z"})

    reloaded = LocalControlPlaneRepository(state_path)
    snapshot = reloaded.snapshot()

    assert snapshot["users"]["user-1"]["email"] == "owner@example.com"
    assert snapshot["users"]["user-1"]["display_name"] == "Owner Updated"
    assert snapshot["users"]["user-1"]["created_at"] == user["created_at"]
    assert snapshot["workspaces"]["workspace-1"]["name"] == "Primary"
    assert snapshot["workspaces"]["workspace-1"]["app_id"] == "boring-ui"
    assert snapshot["memberships"]["membership-1"]["role"] == "owner"
    assert snapshot["invites"]["invite-1"]["email"] == "editor@example.com"
    assert snapshot["workspace_settings"]["workspace-1"]["theme"] == "light"
    assert snapshot["workspace_runtime"]["workspace-1"]["state"] == "ready"


def test_control_plane_repository_normalizes_role_and_runtime_state(tmp_path: Path) -> None:
    state_path = tmp_path / ".boring" / "control-plane" / "state.json"
    repo = LocalControlPlaneRepository(state_path)

    member = repo.upsert_membership(
        "membership-1",
        {"workspace_id": "workspace-1", "user_id": "user-1", "role": "superadmin"},
    )
    invite = repo.upsert_invite(
        "invite-1",
        {"workspace_id": "workspace-1", "email": "viewer@example.com", "role": "invalid"},
    )
    runtime = repo.set_workspace_runtime("workspace-1", {"state": "booting"})

    assert member["role"] == "editor"
    assert invite["role"] == "editor"
    assert runtime["state"] == "pending"


def test_control_plane_router_mounted_in_app_factory(tmp_path: Path) -> None:
    config = APIConfig(workspace_root=tmp_path)
    app = create_app(config=config, include_pty=False, include_stream=False, include_approval=False)
    client = TestClient(app)

    response = client.get("/api/v1/control-plane/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["storage"] == "local-json"
    assert payload["state_path"] == ".boring/control-plane/state.json"
    assert payload["counts"]["workspaces"] == 0

    capabilities = client.get("/api/capabilities").json()
    assert capabilities["features"]["control_plane"] is True


def test_control_plane_http_mutation_endpoints_round_trip(tmp_path: Path) -> None:
    config = APIConfig(workspace_root=tmp_path)
    app = create_app(config=config, include_pty=False, include_stream=False, include_approval=False)
    client = TestClient(app)

    checks = [
        ("/api/v1/control-plane/users/user-1", {"email": "owner@example.com"}),
        ("/api/v1/control-plane/workspaces/workspace-1", {"name": "Primary", "created_by": "user-1"}),
        (
            "/api/v1/control-plane/memberships/membership-1",
            {"workspace_id": "workspace-1", "user_id": "user-1", "role": "owner"},
        ),
        (
            "/api/v1/control-plane/invites/invite-1",
            {"workspace_id": "workspace-1", "email": "editor@example.com", "role": "editor"},
        ),
        ("/api/v1/control-plane/workspaces/workspace-1/settings", {"theme": "light"}),
        ("/api/v1/control-plane/workspaces/workspace-1/runtime", {"state": "ready"}),
    ]
    for path, payload in checks:
        response = client.put(path, json={"data": payload})
        assert response.status_code == 200, response.text

    bad_shape = client.put("/api/v1/control-plane/users/user-2", json={"email": "missing-wrapper@example.com"})
    assert bad_shape.status_code == 422

    snapshot = client.get("/api/v1/control-plane/snapshot")
    assert snapshot.status_code == 200
    data = snapshot.json()["snapshot"]
    assert data["users"]["user-1"]["email"] == "owner@example.com"
    assert data["workspaces"]["workspace-1"]["name"] == "Primary"
    assert data["memberships"]["membership-1"]["role"] == "owner"
    assert data["invites"]["invite-1"]["email"] == "editor@example.com"
    assert data["workspace_settings"]["workspace-1"]["theme"] == "light"
    assert data["workspace_runtime"]["workspace-1"]["state"] == "ready"

    users = client.get("/api/v1/control-plane/users")
    workspaces = client.get("/api/v1/control-plane/workspaces")
    memberships = client.get("/api/v1/control-plane/memberships")
    invites = client.get("/api/v1/control-plane/invites")
    settings = client.get("/api/v1/control-plane/workspaces/workspace-1/settings")
    runtime = client.get("/api/v1/control-plane/workspaces/workspace-1/runtime")
    assert users.status_code == 200
    assert workspaces.status_code == 200
    assert memberships.status_code == 200
    assert invites.status_code == 200
    assert settings.status_code == 200
    assert runtime.status_code == 200
    assert users.json()["count"] == 1
    assert workspaces.json()["count"] == 1
    assert memberships.json()["count"] == 1
    assert invites.json()["count"] == 1
    assert settings.json()["settings"]["theme"] == "light"
    assert runtime.json()["runtime"]["state"] == "ready"


def test_control_plane_policy_enforcement_for_delegated_claims(tmp_path: Path) -> None:
    config = APIConfig(workspace_root=tmp_path)
    app = create_app(config=config, include_pty=False, include_stream=False, include_approval=False)
    client = TestClient(app)

    denied_write = client.put(
        "/api/v1/control-plane/users/user-1",
        json={"data": {"email": "owner@example.com"}},
        headers=_scope_headers(["workspace.files.read"]),
    )
    assert denied_write.status_code == 403
    assert denied_write.json()["code"] == "capability_denied"

    denied_read = client.get(
        "/api/v1/control-plane/users",
        headers=_scope_headers(["workspace.files.write"]),
    )
    assert denied_read.status_code == 403
    assert denied_read.json()["code"] == "capability_denied"


def test_control_plane_repository_moves_corrupt_json_to_backup(tmp_path: Path) -> None:
    state_path = tmp_path / ".boring" / "control-plane" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{not-json", encoding="utf-8")

    repo = LocalControlPlaneRepository(state_path)
    snapshot = repo.snapshot()

    assert snapshot == {
        "users": {},
        "workspaces": {},
        "memberships": {},
        "invites": {},
        "workspace_settings": {},
        "workspace_runtime": {},
    }
    backups = list(state_path.parent.glob("state.json.corrupt-*"))
    assert backups, "Expected invalid state file to be moved to a .corrupt-* backup"
    assert state_path.exists() is False


def test_control_plane_router_can_be_disabled_in_app_factory(tmp_path: Path) -> None:
    config = APIConfig(workspace_root=tmp_path, control_plane_enabled=False)
    app = create_app(config=config, include_pty=False, include_stream=False, include_approval=False)
    client = TestClient(app)

    response = client.get("/api/v1/control-plane/health")
    assert response.status_code == 404

    capabilities = client.get("/api/capabilities").json()
    assert capabilities["features"]["control_plane"] is False
