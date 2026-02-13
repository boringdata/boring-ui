"""Unit tests for session workspace selection route.

Bead: bd-1joj.6 (SESS0)

Tests POST /api/v1/session/workspace against InMemory repos.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from control_plane.app.main import create_app
from control_plane.app.settings import ControlPlaneSettings
from control_plane.app.routes.session import _sign_cookie, _verify_cookie


def _make_app():
    """Create a test app with InMemory repos and session router wired in."""
    settings = ControlPlaneSettings(environment="local")
    return create_app(settings)


async def _seed_workspace(app, workspace_id: str, user_id: str):
    """Create a workspace and active membership in InMemory repos."""
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
        "status": "active",
    })


# ── Test: POST sets active workspace and returns next_path ──────────


class TestSetSessionWorkspace:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)

        # Seed data (run async in sync context)
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            _seed_workspace(self.app, "ws_test1", "user-1")
        )

    def test_sets_active_workspace_and_returns_next_path(self):
        resp = self.client.post(
            "/api/v1/session/workspace",
            json={"workspace_id": "ws_test1"},
            headers={
                "Authorization": "Bearer test-token",
                "X-User-ID": "user-1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_id"] == "ws_test1"
        assert data["next_path"] == "/w/ws_test1/app"

    def test_response_includes_role_and_runtime_state(self):
        resp = self.client.post(
            "/api/v1/session/workspace",
            json={"workspace_id": "ws_test1"},
            headers={
                "Authorization": "Bearer test-token",
                "X-User-ID": "user-1",
            },
        )
        data = resp.json()
        assert data["role"] == "admin"
        assert data["runtime_state"] in ("provisioning", "ready", "error")

    def test_403_if_not_a_member(self):
        resp = self.client.post(
            "/api/v1/session/workspace",
            json={"workspace_id": "ws_test1"},
            headers={
                "Authorization": "Bearer test-token",
                "X-User-ID": "non-member-user",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "FORBIDDEN"

    def test_404_if_workspace_not_found(self):
        resp = self.client.post(
            "/api/v1/session/workspace",
            json={"workspace_id": "ws_nonexistent"},
            headers={
                "Authorization": "Bearer test-token",
                "X-User-ID": "user-1",
            },
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "WORKSPACE_NOT_FOUND"

    def test_cookie_set_on_success(self):
        resp = self.client.post(
            "/api/v1/session/workspace",
            json={"workspace_id": "ws_test1"},
            headers={
                "Authorization": "Bearer test-token",
                "X-User-ID": "user-1",
            },
        )
        assert resp.status_code == 200
        # Check Set-Cookie header
        assert "boring-session" in resp.cookies

    def test_cookie_flags_httponly_samesite(self):
        resp = self.client.post(
            "/api/v1/session/workspace",
            json={"workspace_id": "ws_test1"},
            headers={
                "Authorization": "Bearer test-token",
                "X-User-ID": "user-1",
            },
        )
        # Check raw Set-Cookie header for flags
        set_cookie = resp.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower()
        assert "samesite=lax" in set_cookie.lower()

    def test_401_without_user_id(self):
        resp = self.client.post(
            "/api/v1/session/workspace",
            json={"workspace_id": "ws_test1"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 401

    def test_400_without_workspace_id(self):
        resp = self.client.post(
            "/api/v1/session/workspace",
            json={},
            headers={
                "Authorization": "Bearer test-token",
                "X-User-ID": "user-1",
            },
        )
        assert resp.status_code == 400


# ── Test: cookie signing/verification ────────────────────────────────


class TestCookieSigning:
    def test_sign_and_verify_roundtrip(self):
        payload = {"active_workspace_id": "ws_1", "user_id": "u1"}
        signed = _sign_cookie(payload, "test-secret")
        verified = _verify_cookie(signed, "test-secret")
        assert verified == payload

    def test_verify_rejects_tampered(self):
        signed = _sign_cookie({"ws": "ws_1"}, "secret")
        tampered = signed[:-1] + ("a" if signed[-1] != "a" else "b")
        assert _verify_cookie(tampered, "secret") is None

    def test_verify_rejects_wrong_secret(self):
        signed = _sign_cookie({"ws": "ws_1"}, "correct-secret")
        assert _verify_cookie(signed, "wrong-secret") is None

    def test_verify_rejects_malformed(self):
        assert _verify_cookie("garbage", "secret") is None
        assert _verify_cookie("", "secret") is None
