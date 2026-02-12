"""Unit tests for OIDC auth middleware and AuthContext (bd-1pwb.10.1).

Tests:
- AuthContext permission matching (exact, wildcard, namespace)
- add_oidc_auth_middleware (bearer extraction, context injection, error semantics)
- get_auth_context helper
- require_permission decorator
- AuthErrorEmitter telemetry and error contract
"""

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import boring_ui.api.auth_middleware as auth_middleware_module

from boring_ui.api.auth_middleware import (
    AuthContext,
    add_oidc_auth_middleware,
    get_auth_context,
    require_permission,
)
from boring_ui.api.auth_middleware import AuthErrorEmitter, AuthErrorTelemetry


# --- AuthContext ---

class TestAuthContext:
    """AuthContext creation and permission matching."""

    def test_basic_creation(self):
        ctx = AuthContext(user_id="u1", workspace_id="ws1", permissions={"files:read"})
        assert ctx.user_id == "u1"
        assert ctx.workspace_id == "ws1"
        assert "files:read" in ctx.permissions

    def test_exact_permission_match(self):
        ctx = AuthContext(user_id="u1", permissions={"files:read", "git:status"})
        assert ctx.has_permission("files:read") is True
        assert ctx.has_permission("git:status") is True
        assert ctx.has_permission("exec:run") is False

    def test_wildcard_all_permissions(self):
        ctx = AuthContext(user_id="u1", permissions={"*"})
        assert ctx.has_permission("files:read") is True
        assert ctx.has_permission("exec:run") is True
        assert ctx.has_permission("anything:at_all") is True

    def test_namespace_wildcard(self):
        ctx = AuthContext(user_id="u1", permissions={"git:*"})
        assert ctx.has_permission("git:read") is True
        assert ctx.has_permission("git:status") is True
        assert ctx.has_permission("git:commit") is True
        assert ctx.has_permission("files:read") is False

    def test_multiple_namespace_wildcards(self):
        ctx = AuthContext(user_id="u1", permissions={"git:*", "files:*"})
        assert ctx.has_permission("git:read") is True
        assert ctx.has_permission("files:write") is True
        assert ctx.has_permission("exec:run") is False

    def test_empty_permissions(self):
        ctx = AuthContext(user_id="u1", permissions=set())
        assert ctx.has_permission("files:read") is False

    def test_default_values(self):
        ctx = AuthContext(user_id="u1")
        assert ctx.workspace_id is None
        assert ctx.permissions == set()
        assert ctx.claims == {}


# --- OIDC Auth Middleware ---

class TestOIDCAuthMiddleware:
    """add_oidc_auth_middleware behavior."""

    def _make_app(self, verifier):
        app = FastAPI()
        add_oidc_auth_middleware(app, verifier)

        @app.get("/protected")
        async def protected(request: Request):
            ctx = request.state.auth_context
            return {"user": ctx.user_id, "workspace": ctx.workspace_id}

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return app

    def _make_verifier(self, claims=None):
        verifier = MagicMock()
        verifier.issuer_url = "https://test.example.com"
        verifier.verify_token.return_value = claims
        return verifier

    def test_missing_auth_header_returns_401(self):
        verifier = self._make_verifier()
        app = self._make_app(verifier)
        tc = TestClient(app)

        resp = tc.get("/protected")
        assert resp.status_code == 401
        data = resp.json()
        assert data["code"] == "AUTH_MISSING"
        assert "request_id" in data

    def test_non_bearer_auth_returns_401(self):
        verifier = self._make_verifier()
        app = self._make_app(verifier)
        tc = TestClient(app)

        resp = tc.get("/protected", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_MISSING"

    def test_invalid_token_returns_401(self):
        verifier = self._make_verifier(claims=None)  # Validation fails
        app = self._make_app(verifier)
        tc = TestClient(app)

        resp = tc.get("/protected", headers={"Authorization": "Bearer invalid-jwt"})
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_INVALID"

    def test_valid_token_injects_context(self):
        claims = {
            "sub": "user-123",
            "workspace": "ws-456",
            "permissions": ["files:read", "git:status"],
        }
        verifier = self._make_verifier(claims=claims)
        app = self._make_app(verifier)
        tc = TestClient(app)

        resp = tc.get("/protected", headers={"Authorization": "Bearer valid-jwt"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] == "user-123"
        assert data["workspace"] == "ws-456"

    def test_missing_sub_claim_returns_401(self):
        claims = {"workspace": "ws-456"}  # No 'sub'
        verifier = self._make_verifier(claims=claims)
        app = self._make_app(verifier)
        tc = TestClient(app)

        resp = tc.get("/protected", headers={"Authorization": "Bearer no-sub-jwt"})
        assert resp.status_code == 401

    def test_health_endpoint_bypasses_auth(self):
        verifier = self._make_verifier(claims=None)
        app = self._make_app(verifier)
        tc = TestClient(app)

        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_options_preflight_bypasses_auth(self):
        verifier = self._make_verifier(claims=None)
        app = self._make_app(verifier)
        tc = TestClient(app)

        resp = tc.options("/protected")
        # OPTIONS should not require auth (CORS preflight)
        assert resp.status_code != 401

    def test_permissions_from_string(self):
        claims = {"sub": "u1", "permissions": "files:read git:status exec:run"}
        verifier = self._make_verifier(claims=claims)
        app = self._make_app(verifier)

        @app.get("/perms")
        async def perms(request: Request):
            ctx = request.state.auth_context
            return {"perms": sorted(ctx.permissions)}

        tc = TestClient(app)
        resp = tc.get("/perms", headers={"Authorization": "Bearer tok"})
        assert resp.status_code == 200
        assert set(resp.json()["perms"]) == {"files:read", "git:status", "exec:run"}

    def test_permissions_from_list(self):
        claims = {"sub": "u1", "permissions": ["files:read", "git:status"]}
        verifier = self._make_verifier(claims=claims)
        app = self._make_app(verifier)

        @app.get("/perms")
        async def perms(request: Request):
            ctx = request.state.auth_context
            return {"perms": sorted(ctx.permissions)}

        tc = TestClient(app)
        resp = tc.get("/perms", headers={"Authorization": "Bearer tok"})
        assert resp.status_code == 200
        assert set(resp.json()["perms"]) == {"files:read", "git:status"}

    def test_verifier_none_disables_middleware(self):
        app = FastAPI()
        add_oidc_auth_middleware(app, None)

        @app.get("/test")
        async def test_route():
            return {"status": "ok"}

        tc = TestClient(app)
        resp = tc.get("/test")
        assert resp.status_code == 200

    def test_401_includes_www_authenticate_header(self):
        verifier = self._make_verifier(claims=None)
        app = self._make_app(verifier)
        tc = TestClient(app)

        resp = tc.get("/protected")
        assert "WWW-Authenticate" in resp.headers


# --- get_auth_context ---

class TestGetAuthContext:
    """get_auth_context helper."""

    def test_returns_context_when_present(self):
        app = FastAPI()

        @app.middleware("http")
        async def inject(request, call_next):
            request.state.auth_context = AuthContext(user_id="u1")
            return await call_next(request)

        @app.get("/test")
        async def route(request: Request):
            ctx = get_auth_context(request)
            return {"user": ctx.user_id}

        tc = TestClient(app)
        resp = tc.get("/test")
        assert resp.status_code == 200
        assert resp.json()["user"] == "u1"

    def test_raises_401_when_missing(self):
        app = FastAPI()

        @app.get("/test")
        async def route(request: Request):
            ctx = get_auth_context(request)
            return {"user": ctx.user_id}

        tc = TestClient(app)
        resp = tc.get("/test")
        assert resp.status_code == 401


# --- require_permission ---

class TestRequirePermission:
    """require_permission decorator."""

    def _make_app_with_permissions(self, permissions):
        app = FastAPI()

        @app.middleware("http")
        async def inject(request, call_next):
            request.state.auth_context = AuthContext(
                user_id="u1", permissions=permissions
            )
            return await call_next(request)

        @app.get("/read")
        @require_permission("files:read")
        async def read_route(request: Request):
            return {"ok": True}

        @app.get("/write")
        @require_permission("files:write")
        async def write_route(request: Request):
            return {"ok": True}

        return app

    def test_allows_with_matching_permission(self):
        app = self._make_app_with_permissions({"files:read"})
        tc = TestClient(app)
        resp = tc.get("/read")
        assert resp.status_code == 200

    def test_blocks_without_matching_permission(self):
        app = self._make_app_with_permissions({"files:read"})
        tc = TestClient(app)
        resp = tc.get("/write")
        assert resp.status_code == 403

    def test_wildcard_allows_all(self):
        app = self._make_app_with_permissions({"*"})
        tc = TestClient(app)
        assert tc.get("/read").status_code == 200
        assert tc.get("/write").status_code == 200

    def test_namespace_wildcard_allows_namespace(self):
        app = self._make_app_with_permissions({"files:*"})
        tc = TestClient(app)
        assert tc.get("/read").status_code == 200
        assert tc.get("/write").status_code == 200

    def test_403_response_has_error_contract(self):
        app = self._make_app_with_permissions({"chat:read"})
        tc = TestClient(app)
        resp = tc.get("/read")
        assert resp.status_code == 403
        data = resp.json()
        assert data["code"] == "AUTHZ_INSUFFICIENT"
        assert "required_permission" in data
        assert "request_id" in data

    def test_no_context_returns_401(self):
        """Without middleware injecting context, decorator returns 401."""
        app = FastAPI()

        @app.get("/test")
        @require_permission("files:read")
        async def route(request: Request):
            return {"ok": True}

        tc = TestClient(app)
        resp = tc.get("/test")
        assert resp.status_code == 401


# --- AuthErrorEmitter ---

class TestAuthErrorEmitter:
    """AuthErrorEmitter error contract and telemetry."""

    def test_missing_token_returns_401(self):
        emitter = AuthErrorEmitter()
        resp = emitter.missing_token("/api/test")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self):
        emitter = AuthErrorEmitter()
        resp = emitter.invalid_token("/api/test")
        assert resp.status_code == 401

    def test_insufficient_permission_returns_403(self):
        emitter = AuthErrorEmitter()
        resp = emitter.insufficient_permission("/api/test", "u1", "files:read", {"chat:read"})
        assert resp.status_code == 403

    def test_telemetry_counters(self):
        emitter = AuthErrorEmitter()
        emitter.missing_token("/a")
        emitter.missing_token("/b")
        emitter.invalid_token("/c")
        emitter.insufficient_permission("/d", "u1", "x", set())
        emitter.insufficient_permission("/e", "u2", "y", set())
        emitter.insufficient_permission("/f", "u3", "z", set())

        stats = emitter.get_stats()
        assert stats["authn_missing"] == 2
        assert stats["authn_invalid"] == 1
        assert stats["authz_insufficient"] == 3
        assert stats["total_failures"] == 6

    def test_request_id_in_error_response(self):
        emitter = AuthErrorEmitter()
        resp = emitter.missing_token("/test", request_id="req-123")
        # Parse body to check content
        import json
        body = json.loads(resp.body.decode())
        assert body["request_id"] == "req-123"

    def test_auto_generated_request_id(self):
        emitter = AuthErrorEmitter()
        resp = emitter.missing_token("/test")
        import json
        body = json.loads(resp.body.decode())
        assert len(body["request_id"]) > 0  # UUID auto-generated


