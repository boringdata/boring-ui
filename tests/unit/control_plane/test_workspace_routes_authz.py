"""Unit tests for workspace-scoped route authorization.

Bead: bd-1joj.12 (AUTHZ0)

Tests that workspace-scoped endpoints enforce membership authorization
via HTTP requests against the test app with InMemory repos.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from control_plane.app.main import create_app
from control_plane.app.settings import ControlPlaneSettings


def _make_app():
    settings = ControlPlaneSettings(environment="local")
    return create_app(settings)


async def _seed_workspace(app, workspace_id: str, user_id: str, member_status: str = "active"):
    deps = app.state.deps
    await deps.workspace_repo.create({
        "id": workspace_id,
        "name": "Test Workspace",
        "owner_id": user_id,
        "app_id": "boring-ui",
    })
    await deps.member_repo.add_member(workspace_id, {
        "user_id": user_id,
        "email": "test@example.com",
        "role": "admin",
        "status": member_status,
    })


def _auth_headers(user_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-User-ID": user_id,
    }


# Workspace-scoped endpoints to test (method, path_template)
WORKSPACE_SCOPED_ENDPOINTS = [
    ("GET", "/api/v1/workspaces/{ws_id}"),
    ("PATCH", "/api/v1/workspaces/{ws_id}"),
    ("GET", "/api/v1/workspaces/{ws_id}/members"),
    ("POST", "/api/v1/workspaces/{ws_id}/members"),
    ("DELETE", "/api/v1/workspaces/{ws_id}/members/mem_fake"),
    ("GET", "/api/v1/workspaces/{ws_id}/runtime"),
    ("POST", "/api/v1/workspaces/{ws_id}/retry"),
    ("POST", "/api/v1/workspaces/{ws_id}/shares"),
    ("DELETE", "/api/v1/workspaces/{ws_id}/shares/shr_fake"),
]


class TestWorkspaceAuthzEnforcement:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)
        asyncio.get_event_loop().run_until_complete(
            _seed_workspace(self.app, "ws_test", "user-1")
        )

    # ── Active member gets through (501 from stub, but NOT 403) ──

    @pytest.mark.parametrize("method,path_template", WORKSPACE_SCOPED_ENDPOINTS)
    def test_active_member_passes_authz(self, method, path_template):
        path = path_template.replace("{ws_id}", "ws_test")
        resp = self.client.request(method, path, headers=_auth_headers("user-1"))
        # Should get 501 (stub) not 403 (authz fail)
        assert resp.status_code == 501, f"{method} {path}: expected 501, got {resp.status_code}"

    # ── Non-member gets 403 ──────────────────────────────────────

    @pytest.mark.parametrize("method,path_template", WORKSPACE_SCOPED_ENDPOINTS)
    def test_non_member_gets_403(self, method, path_template):
        path = path_template.replace("{ws_id}", "ws_test")
        resp = self.client.request(method, path, headers=_auth_headers("user-other"))
        assert resp.status_code == 403, f"{method} {path}: expected 403, got {resp.status_code}"
        assert resp.json()["detail"]["code"] == "FORBIDDEN"

    # ── Nonexistent workspace gets 404 ───────────────────────────

    @pytest.mark.parametrize("method,path_template", WORKSPACE_SCOPED_ENDPOINTS)
    def test_nonexistent_workspace_gets_404(self, method, path_template):
        path = path_template.replace("{ws_id}", "ws_nonexistent")
        resp = self.client.request(method, path, headers=_auth_headers("user-1"))
        assert resp.status_code == 404, f"{method} {path}: expected 404, got {resp.status_code}"
        assert resp.json()["detail"]["code"] == "WORKSPACE_NOT_FOUND"


class TestRemovedMemberForbidden:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)
        asyncio.get_event_loop().run_until_complete(
            _seed_workspace(self.app, "ws_test", "user-removed", member_status="removed")
        )

    def test_removed_member_gets_403_on_get_workspace(self):
        resp = self.client.get(
            "/api/v1/workspaces/ws_test",
            headers=_auth_headers("user-removed"),
        )
        assert resp.status_code == 403

    def test_removed_member_gets_403_on_list_members(self):
        resp = self.client.get(
            "/api/v1/workspaces/ws_test/members",
            headers=_auth_headers("user-removed"),
        )
        assert resp.status_code == 403


class TestPendingMemberForbidden:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)
        asyncio.get_event_loop().run_until_complete(
            _seed_workspace(self.app, "ws_test", "user-pending", member_status="pending")
        )

    def test_pending_member_gets_403_on_get_workspace(self):
        resp = self.client.get(
            "/api/v1/workspaces/ws_test",
            headers=_auth_headers("user-pending"),
        )
        assert resp.status_code == 403

    def test_pending_member_gets_403_on_patch_workspace(self):
        resp = self.client.patch(
            "/api/v1/workspaces/ws_test",
            headers=_auth_headers("user-pending"),
        )
        assert resp.status_code == 403


class TestCrossTenantIsolation:
    """Security tests: user A cannot access user B's workspace."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)
        asyncio.get_event_loop().run_until_complete(self._seed_two_tenants())

    async def _seed_two_tenants(self):
        await _seed_workspace(self.app, "ws_a", "user-a")
        await _seed_workspace(self.app, "ws_b", "user-b")

    def test_user_a_cannot_get_workspace_b(self):
        resp = self.client.get(
            "/api/v1/workspaces/ws_b",
            headers=_auth_headers("user-a"),
        )
        assert resp.status_code == 403

    def test_user_b_cannot_patch_workspace_a(self):
        resp = self.client.patch(
            "/api/v1/workspaces/ws_a",
            headers=_auth_headers("user-b"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_list_members_of_workspace_b(self):
        resp = self.client.get(
            "/api/v1/workspaces/ws_b/members",
            headers=_auth_headers("user-a"),
        )
        assert resp.status_code == 403

    def test_user_a_cannot_create_share_in_workspace_b(self):
        resp = self.client.post(
            "/api/v1/workspaces/ws_b/shares",
            headers=_auth_headers("user-a"),
        )
        assert resp.status_code == 403

    def test_user_a_can_access_own_workspace(self):
        resp = self.client.get(
            "/api/v1/workspaces/ws_a",
            headers=_auth_headers("user-a"),
        )
        # 501 = stub, not 403 = authz passed
        assert resp.status_code == 501

    def test_user_b_can_access_own_workspace(self):
        resp = self.client.get(
            "/api/v1/workspaces/ws_b",
            headers=_auth_headers("user-b"),
        )
        assert resp.status_code == 501
