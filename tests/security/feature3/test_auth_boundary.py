"""Security regression: authentication boundary tests.

Bead: bd-1joj.26 (TEST-SEC)

Verifies that authentication is enforced at system boundaries:
- Protected endpoints require auth (401 not 500)
- Forged/spoofed headers are rejected
- Cookie signing is tamper-proof
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from control_plane.app.main import create_app
from control_plane.app.settings import ControlPlaneSettings
from control_plane.app.routes.session import _sign_cookie, _verify_cookie


def _make_app():
    return create_app(ControlPlaneSettings(environment="local"))


# ── Unauthenticated access returns 401 ────────────────────────────────


class TestUnauthenticatedReturns401:
    """Protected endpoints must return 401 (not 500) when unauthenticated."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/v1/me"),
        ("GET", "/api/v1/workspaces"),
        ("POST", "/api/v1/workspaces"),
        ("GET", "/api/v1/workspaces/ws_1"),
        ("PATCH", "/api/v1/workspaces/ws_1"),
        ("GET", "/api/v1/workspaces/ws_1/members"),
        ("POST", "/api/v1/workspaces/ws_1/members"),
        ("DELETE", "/api/v1/workspaces/ws_1/members/mem_1"),
        ("POST", "/api/v1/session/workspace"),
        ("GET", "/api/v1/workspaces/ws_1/runtime"),
        ("POST", "/api/v1/workspaces/ws_1/retry"),
    ]

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_no_auth_returns_401(self, method, path):
        """Every protected endpoint returns 401 without auth, never 500."""
        resp = self.client.request(method, path)
        assert resp.status_code == 401, (
            f"{method} {path}: expected 401, got {resp.status_code}"
        )


# ── Auth-exempt endpoints (allowlist) ─────────────────────────────────


class TestAuthExemptEndpoints:
    """Certain endpoints do not require authentication."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.app = _make_app()
        self.client = TestClient(self.app)

    def test_health_allowed_without_auth(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200

    def test_app_config_allowed_without_auth(self):
        resp = self.client.get("/api/v1/app-config")
        assert resp.status_code == 200

    def test_auth_login_allowed_without_auth(self):
        resp = self.client.post("/auth/login")
        # 501 (not implemented) is acceptable, but NOT 401
        assert resp.status_code != 401

    def test_auth_callback_allowed_without_auth(self):
        resp = self.client.get("/auth/callback")
        assert resp.status_code != 401

    def test_options_preflight_always_allowed(self):
        resp = self.client.options("/api/v1/workspaces")
        assert resp.status_code != 401


# ── Header spoofing prevention ────────────────────────────────────────


class TestHeaderSpoofing:
    """Browser-sent internal headers must be stripped by the proxy."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from control_plane.app.routing.proxy import _sanitize_request_headers
        self._sanitize = _sanitize_request_headers

    def test_authorization_replaced_with_sprite_token(self):
        """Browser Authorization header is replaced, not forwarded."""
        result = self._sanitize(
            {"Authorization": "Bearer user-stolen-token"},
            sprite_bearer_token="sprite-real-token",
        )
        assert result["Authorization"] == "Bearer sprite-real-token"

    def test_x_sprite_token_stripped(self):
        result = self._sanitize(
            {"X-Sprite-Token": "forged", "Content-Type": "application/json"},
            sprite_bearer_token="sprite-real-token",
        )
        assert "X-Sprite-Token" not in result

    def test_x_service_token_stripped(self):
        result = self._sanitize(
            {"X-Service-Token": "forged", "Accept": "application/json"},
            sprite_bearer_token="sprite-real-token",
        )
        assert "X-Service-Token" not in result

    def test_x_internal_auth_stripped(self):
        result = self._sanitize(
            {"X-Internal-Auth": "forged"},
            sprite_bearer_token="sprite-real-token",
        )
        assert "X-Internal-Auth" not in result

    def test_host_header_stripped(self):
        """Host header must not be forwarded to prevent host-header attacks."""
        result = self._sanitize(
            {"Host": "evil.com"},
            sprite_bearer_token="sprite-real-token",
        )
        assert "Host" not in result


# ── Session cookie tampering ──────────────────────────────────────────


class TestSessionCookieTampering:
    """Signed session cookies must be tamper-proof."""

    def test_valid_cookie_verifies(self):
        payload = {"active_workspace_id": "ws_1", "user_id": "user-1"}
        signed = _sign_cookie(payload, "my-secret")
        result = _verify_cookie(signed, "my-secret")
        assert result == payload

    def test_tampered_payload_rejected(self):
        signed = _sign_cookie({"ws": "ws_1"}, "secret")
        # Flip one character in the signature
        tampered = signed[:-1] + ("a" if signed[-1] != "a" else "b")
        assert _verify_cookie(tampered, "secret") is None

    def test_wrong_secret_rejected(self):
        signed = _sign_cookie({"ws": "ws_1"}, "correct")
        assert _verify_cookie(signed, "wrong") is None

    def test_garbage_input_rejected(self):
        assert _verify_cookie("not-a-cookie", "secret") is None
        assert _verify_cookie("", "secret") is None
        assert _verify_cookie("a.b.c.d", "secret") is None

    def test_no_dot_separator_rejected(self):
        assert _verify_cookie("nodots", "secret") is None
