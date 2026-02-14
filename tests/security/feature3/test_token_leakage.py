"""Security regression: token/credential leakage tests.

Bead: bd-1joj.26 (TEST-SEC)

Verifies that sensitive credentials are never exposed to browsers:
- SPRITE_BEARER_TOKEN never in proxy responses
- Share link plaintext token never persisted (only hash)
- SESSION_SECRET never in responses
- Audit emitter sanitizes credentials
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from control_plane.app.main import create_app
from control_plane.app.settings import ControlPlaneSettings
from control_plane.app.db.audit_emitter import _sanitize_payload


# ── Audit sanitization ────────────────────────────────────────────────


class TestAuditSanitization:
    def test_sanitizes_bearer_token(self):
        result = _sanitize_payload({"authorization": "Bearer secret"})
        assert result["authorization"] == "[REDACTED]"

    def test_sanitizes_apikey(self):
        result = _sanitize_payload({"apikey": "sk-1234"})
        assert result["apikey"] == "[REDACTED]"

    def test_sanitizes_nested_secrets(self):
        result = _sanitize_payload({
            "headers": {
                "authorization": "Bearer abc",
                "x-request-id": "req-1",
            },
        })
        assert result["headers"]["authorization"] == "[REDACTED]"
        assert result["headers"]["x-request-id"] == "req-1"

    def test_sanitizes_service_role_key(self):
        result = _sanitize_payload({
            "supabase_service_role_key": "eyJhbGc...",
            "url": "https://test.supabase.co",
        })
        assert result["supabase_service_role_key"] == "[REDACTED]"
        assert result["url"] == "https://test.supabase.co"

    def test_sanitizes_password(self):
        result = _sanitize_payload({"password": "hunter2", "user": "admin"})
        assert result["password"] == "[REDACTED]"
        assert result["user"] == "admin"

    def test_sanitizes_sprite_bearer_token(self):
        result = _sanitize_payload({"sprite_bearer_token": "spr-secret"})
        assert result["sprite_bearer_token"] == "[REDACTED]"


# ── Share link token storage ──────────────────────────────────────────


class TestShareTokenNotStored:
    """Plaintext share tokens should never be persisted."""

    @pytest.mark.asyncio
    async def test_create_share_stores_hash_not_plaintext(self):
        import hashlib
        seen: dict[str, Any] = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(201, json=[{"id": "shr_1"}])

        from control_plane.app.db.supabase_client import SupabaseClient
        from control_plane.app.db.share_repo import SupabaseShareLinkRepository

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        sc = SupabaseClient(
            supabase_url="https://test.supabase.co",
            service_role_key="svc-key",
            http_client=client,
        )
        repo = SupabaseShareLinkRepository(sc)
        result = await repo.create_share({
            "workspace_id": "ws_1",
            "path": "/file.txt",
            "access": "read",
            "created_by": "user-1",
        })

        # Plaintext token returned to caller
        assert "token" in result
        # DB payload has hash, NOT plaintext
        assert "token_hash" in seen["body"]
        assert "token" not in seen["body"]
        # Hash matches
        expected_hash = hashlib.sha256(result["token"].encode()).hexdigest()
        assert seen["body"]["token_hash"] == expected_hash


# ── Proxy response header leakage ─────────────────────────────────────


class TestProxyResponseLeakage:
    """Sprite bearer token must never leak in proxy responses."""

    @pytest.fixture(autouse=True)
    def setup(self):
        app = create_app(ControlPlaneSettings(
            environment="local",
            sprite_bearer_token="sprite-super-secret-token",
        ))
        self.client = TestClient(app)
        self.app = app
        asyncio.get_event_loop().run_until_complete(self._seed())

    async def _seed(self):
        deps = self.app.state.deps
        await deps.workspace_repo.create({
            "id": "ws_1",
            "name": "Test",
            "owner_id": "user-1",
            "app_id": "boring-ui",
        })
        await deps.member_repo.add_member("ws_1", {
            "user_id": "user-1",
            "email": "user@test.com",
            "role": "admin",
            "status": "active",
        })
        await deps.runtime_store.upsert_runtime("ws_1", {
            "state": "ready",
            "sandbox_name": "sbx-test",
        })

    def _headers(self):
        return {"Authorization": "Bearer test-token", "X-User-ID": "user-1"}

    def test_sprite_token_not_in_response_headers(self):
        with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
            mock_response = httpx.Response(
                200,
                json={"files": []},
                headers={
                    "content-type": "application/json",
                    "authorization": "Bearer sprite-super-secret-token",
                    "x-sprite-token": "sprite-super-secret-token",
                },
            )
            instance = AsyncMock()
            instance.request = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            resp = self.client.get("/w/ws_1/api/v1/files/list", headers=self._headers())

        # Sprite token must be stripped from response
        for key, value in resp.headers.items():
            assert "sprite-super-secret-token" not in value, (
                f"Sprite token leaked in response header {key}: {value}"
            )

    def test_sprite_token_not_in_response_body(self):
        with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
            mock_response = httpx.Response(200, json={"data": "safe"})
            instance = AsyncMock()
            instance.request = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            resp = self.client.get("/w/ws_1/api/v1/files/list", headers=self._headers())

        assert "sprite-super-secret-token" not in resp.text

    def test_set_cookie_stripped_from_proxy_response(self):
        """Workspace plane must not set cookies on control-plane domain."""
        with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
            mock_response = httpx.Response(
                200,
                json={},
                headers={
                    "content-type": "application/json",
                    "set-cookie": "session=evil; HttpOnly",
                },
            )
            instance = AsyncMock()
            instance.request = AsyncMock(return_value=mock_response)
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            resp = self.client.get("/w/ws_1/api/v1/files/list", headers=self._headers())

        assert "set-cookie" not in resp.headers


# ── Session secret leakage ────────────────────────────────────────────


class TestSessionSecretLeakage:
    """SESSION_SECRET must never appear in HTTP responses."""

    def test_session_secret_not_in_config_response(self):
        app = create_app(ControlPlaneSettings(environment="local"))
        client = TestClient(app)
        resp = client.get("/api/v1/app-config")
        assert resp.status_code == 200
        assert "local-dev-secret" not in resp.text
        assert "session_secret" not in resp.text

    def test_session_secret_not_in_health_response(self):
        app = create_app(ControlPlaneSettings(environment="local"))
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert "session_secret" not in resp.text
