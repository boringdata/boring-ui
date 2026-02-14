"""Security regression: tenant isolation tests.

Bead: bd-1joj.26 (TEST-SEC)

Verifies that workspace-scoped endpoints enforce strict tenant boundaries:
- User A cannot access User B's workspace via any endpoint
- Removed/pending members are forbidden
- Non-existent workspaces return 404
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from control_plane.app.main import create_app
from control_plane.app.settings import ControlPlaneSettings


def _make_app():
    return create_app(ControlPlaneSettings(environment="local"))


def _auth(user_id: str) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-User-ID": user_id}


async def _seed_tenants(app):
    """Create two workspaces with separate owners."""
    deps = app.state.deps
    await deps.workspace_repo.create({
        "id": "ws_alice",
        "name": "Alice Workspace",
        "owner_id": "alice",
        "app_id": "boring-ui",
    })
    await deps.member_repo.add_member("ws_alice", {
        "user_id": "alice",
        "email": "alice@example.com",
        "role": "admin",
        "status": "active",
    })

    await deps.workspace_repo.create({
        "id": "ws_bob",
        "name": "Bob Workspace",
        "owner_id": "bob",
        "app_id": "boring-ui",
    })
    await deps.member_repo.add_member("ws_bob", {
        "user_id": "bob",
        "email": "bob@example.com",
        "role": "admin",
        "status": "active",
    })


async def _seed_removed_member(app):
    deps = app.state.deps
    await deps.workspace_repo.create({
        "id": "ws_removed",
        "name": "Removed Test",
        "owner_id": "owner",
        "app_id": "boring-ui",
    })
    await deps.member_repo.add_member("ws_removed", {
        "user_id": "removed-user",
        "email": "removed@example.com",
        "role": "admin",
        "status": "removed",
    })


async def _seed_pending_member(app):
    deps = app.state.deps
    await deps.workspace_repo.create({
        "id": "ws_pending",
        "name": "Pending Test",
        "owner_id": "owner",
        "app_id": "boring-ui",
    })
    await deps.member_repo.add_member("ws_pending", {
        "user_id": "pending-user",
        "email": "pending@example.com",
        "role": "admin",
        "status": "pending",
    })


# ── Cross-tenant isolation ────────────────────────────────────────────


class TestCrossTenantIsolation:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)
        asyncio.get_event_loop().run_until_complete(_seed_tenants(self.app))

    def test_alice_cannot_get_bob_workspace(self):
        resp = self.client.get("/api/v1/workspaces/ws_bob", headers=_auth("alice"))
        assert resp.status_code == 403

    def test_alice_cannot_patch_bob_workspace(self):
        resp = self.client.patch("/api/v1/workspaces/ws_bob", headers=_auth("alice"))
        assert resp.status_code == 403

    def test_alice_cannot_list_bob_members(self):
        resp = self.client.get("/api/v1/workspaces/ws_bob/members", headers=_auth("alice"))
        assert resp.status_code == 403

    def test_alice_cannot_add_member_to_bob_workspace(self):
        resp = self.client.post("/api/v1/workspaces/ws_bob/members", headers=_auth("alice"))
        assert resp.status_code == 403

    def test_alice_cannot_create_share_in_bob_workspace(self):
        resp = self.client.post("/api/v1/workspaces/ws_bob/shares", headers=_auth("alice"))
        assert resp.status_code == 403

    def test_alice_cannot_get_bob_runtime(self):
        resp = self.client.get("/api/v1/workspaces/ws_bob/runtime", headers=_auth("alice"))
        assert resp.status_code == 403

    def test_alice_cannot_retry_bob_provisioning(self):
        resp = self.client.post("/api/v1/workspaces/ws_bob/retry", headers=_auth("alice"))
        assert resp.status_code == 403

    def test_alice_cannot_delete_bob_share(self):
        resp = self.client.delete(
            "/api/v1/workspaces/ws_bob/shares/shr_fake",
            headers=_auth("alice"),
        )
        assert resp.status_code == 403

    def test_bob_can_access_own_workspace(self):
        resp = self.client.get("/api/v1/workspaces/ws_bob", headers=_auth("bob"))
        # 501 = stub (authz passed)
        assert resp.status_code == 501

    def test_alice_can_access_own_workspace(self):
        resp = self.client.get("/api/v1/workspaces/ws_alice", headers=_auth("alice"))
        assert resp.status_code == 501


# ── Removed member forbidden ──────────────────────────────────────────


class TestRemovedMemberForbidden:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)
        asyncio.get_event_loop().run_until_complete(_seed_removed_member(self.app))

    def test_removed_cannot_get_workspace(self):
        resp = self.client.get("/api/v1/workspaces/ws_removed", headers=_auth("removed-user"))
        assert resp.status_code == 403

    def test_removed_cannot_list_members(self):
        resp = self.client.get(
            "/api/v1/workspaces/ws_removed/members",
            headers=_auth("removed-user"),
        )
        assert resp.status_code == 403

    def test_removed_cannot_create_share(self):
        resp = self.client.post(
            "/api/v1/workspaces/ws_removed/shares",
            headers=_auth("removed-user"),
        )
        assert resp.status_code == 403


# ── Pending member forbidden ──────────────────────────────────────────


class TestPendingMemberForbidden:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)
        asyncio.get_event_loop().run_until_complete(_seed_pending_member(self.app))

    def test_pending_cannot_get_workspace(self):
        resp = self.client.get("/api/v1/workspaces/ws_pending", headers=_auth("pending-user"))
        assert resp.status_code == 403

    def test_pending_cannot_patch_workspace(self):
        resp = self.client.patch(
            "/api/v1/workspaces/ws_pending",
            headers=_auth("pending-user"),
        )
        assert resp.status_code == 403


# ── Non-existent workspace sanity ─────────────────────────────────────


class TestNonExistentWorkspace:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)

    def test_get_nonexistent_workspace_returns_404(self):
        resp = self.client.get(
            "/api/v1/workspaces/ws_nonexistent",
            headers=_auth("any-user"),
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "WORKSPACE_NOT_FOUND"

    def test_patch_nonexistent_workspace_returns_404(self):
        resp = self.client.patch(
            "/api/v1/workspaces/ws_nonexistent",
            headers=_auth("any-user"),
        )
        assert resp.status_code == 404
