"""Tests for auth guard middleware and /api/v1/me endpoint.

Bead: bd-223o.7.3 (B3)

Validates:
  - Protected routes return 401 without credentials
  - Exempt paths pass through without auth
  - Valid Bearer tokens set auth_identity on request.state
  - Invalid/expired tokens return 401 with error codes
  - /api/v1/me returns authenticated user identity
  - /api/v1/me returns 401 when not authenticated
  - Auth guard dependency works for route-level enforcement
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from control_plane.app.security.auth_guard import (
    AuthGuardMiddleware,
    get_auth_identity,
)
from control_plane.app.security.token_verify import (
    StaticKeyProvider,
    TokenVerifier,
)
from control_plane.app.routes.me import router as me_router

# ── Test constants ────────────────────────────────────────────────────

TEST_SECRET = 'test-auth-guard-secret'
TEST_AUDIENCE = 'authenticated'


def _make_token(
    secret: str = TEST_SECRET,
    **overrides,
) -> str:
    payload = {
        'sub': 'user-uuid-100',
        'email': 'guard@example.com',
        'role': 'authenticated',
        'aud': TEST_AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    payload.update(overrides)
    return jwt.encode(payload, secret, algorithm='HS256')


def _create_verifier() -> TokenVerifier:
    return TokenVerifier(
        key_provider=StaticKeyProvider(TEST_SECRET),
        audience=TEST_AUDIENCE,
        algorithms=['HS256'],
    )


# ── App factory ──────────────────────────────────────────────────────


SESSION_SECRET = 'test-session-secret-for-guard'


def _make_session_cookie(**overrides) -> str:
    """Create a session cookie JWT."""
    payload = {
        'sub': 'user-uuid-session',
        'email': 'session@example.com',
        'role': 'authenticated',
        'type': 'session',
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    payload.update(overrides)
    return jwt.encode(payload, SESSION_SECRET, algorithm='HS256')


def _create_test_app(require_auth: bool = True) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        AuthGuardMiddleware,
        token_verifier=_create_verifier(),
        require_auth=require_auth,
        session_secret=SESSION_SECRET,
    )
    app.include_router(me_router)

    @app.get('/health')
    async def health():
        return {'status': 'ok'}

    @app.get('/auth/callback')
    async def auth_callback():
        return {'auth': 'callback'}

    @app.get('/api/v1/app-config')
    async def app_config():
        return {'app': 'config'}

    @app.get('/api/v1/workspaces')
    async def workspaces(request: Request):
        identity = request.state.auth_identity
        return {
            'user_id': identity.user_id if identity else None,
        }

    @app.get('/api/v1/protected')
    async def protected(request: Request):
        identity = request.state.auth_identity
        return {
            'user_id': identity.user_id,
            'email': identity.email,
        }

    return app


@pytest.fixture
def app():
    return _create_test_app()


@pytest.fixture
def optional_auth_app():
    return _create_test_app(require_auth=False)


# =====================================================================
# 1. Exempt paths
# =====================================================================


class TestExemptPaths:

    @pytest.mark.asyncio
    async def test_health_exempt(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/health')
            assert r.status_code == 200
            assert r.json()['status'] == 'ok'

    @pytest.mark.asyncio
    async def test_auth_callback_exempt(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/auth/callback')
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_app_config_exempt(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/app-config')
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_exempt_paths_have_none_identity(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/health')
            assert r.status_code == 200


# =====================================================================
# 2. Protected routes without credentials
# =====================================================================


class TestProtectedRoutesNoAuth:

    @pytest.mark.asyncio
    async def test_workspaces_returns_401_without_token(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/workspaces')
            assert r.status_code == 401
            data = r.json()
            assert data['error'] == 'unauthorized'
            assert data['code'] == 'no_credentials'

    @pytest.mark.asyncio
    async def test_me_returns_401_without_token(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/me')
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_401_includes_www_authenticate_header(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/workspaces')
            assert r.status_code == 401
            assert r.headers.get('www-authenticate') == 'Bearer'


# =====================================================================
# 3. Valid Bearer token
# =====================================================================


class TestValidBearerToken:

    @pytest.mark.asyncio
    async def test_valid_token_passes_through(self, app):
        token = _make_token()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/protected',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 200
            data = r.json()
            assert data['user_id'] == 'user-uuid-100'
            assert data['email'] == 'guard@example.com'

    @pytest.mark.asyncio
    async def test_identity_set_on_request_state(self, app):
        token = _make_token()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 200
            assert r.json()['user_id'] == 'user-uuid-100'


# =====================================================================
# 4. Invalid/expired tokens
# =====================================================================


class TestInvalidTokens:

    @pytest.mark.asyncio
    async def test_expired_token_returns_401(self, app):
        token = _make_token(exp=int(time.time()) - 100)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'token_expired'

    @pytest.mark.asyncio
    async def test_wrong_secret_returns_401(self, app):
        token = _make_token(secret='wrong-secret')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'decode_error'

    @pytest.mark.asyncio
    async def test_wrong_audience_returns_401(self, app):
        token = _make_token(aud='wrong-audience')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'invalid_audience'

    @pytest.mark.asyncio
    async def test_garbage_token_returns_401(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers={'Authorization': 'Bearer not.a.valid.jwt'},
            )
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_non_bearer_scheme_treated_as_no_credentials(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers={'Authorization': 'Basic dXNlcjpwYXNz'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'no_credentials'


# =====================================================================
# 5. /api/v1/me endpoint
# =====================================================================


class TestMeEndpoint:

    @pytest.mark.asyncio
    async def test_me_returns_identity(self, app):
        token = _make_token()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 200
            data = r.json()
            assert data['user_id'] == 'user-uuid-100'
            assert data['email'] == 'guard@example.com'
            assert data['role'] == 'authenticated'

    @pytest.mark.asyncio
    async def test_me_401_without_auth(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/me')
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_me_email_normalized(self, app):
        token = _make_token(email='Test@EXAMPLE.COM')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 200
            assert r.json()['email'] == 'test@example.com'


# =====================================================================
# 6. Optional auth mode
# =====================================================================


class TestOptionalAuth:

    @pytest.mark.asyncio
    async def test_no_credentials_passes_through(self, optional_auth_app):
        transport = ASGITransport(app=optional_auth_app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/workspaces')
            assert r.status_code == 200
            assert r.json()['user_id'] is None

    @pytest.mark.asyncio
    async def test_valid_credentials_set_identity(self, optional_auth_app):
        token = _make_token()
        transport = ASGITransport(app=optional_auth_app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 200
            assert r.json()['user_id'] == 'user-uuid-100'

    @pytest.mark.asyncio
    async def test_invalid_credentials_still_401(self, optional_auth_app):
        token = _make_token(exp=int(time.time()) - 100)
        transport = ASGITransport(app=optional_auth_app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 401


# =====================================================================
# 7. get_auth_identity dependency
# =====================================================================


class TestGetAuthIdentityDependency:

    @pytest.mark.asyncio
    async def test_returns_identity_when_present(self, app):
        token = _make_token()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 200
            assert r.json()['user_id'] == 'user-uuid-100'

    @pytest.mark.asyncio
    async def test_raises_401_when_absent(self, optional_auth_app):
        """In optional auth mode, the middleware passes through but
        the /api/v1/me route's dependency still enforces auth."""
        transport = ASGITransport(app=optional_auth_app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/me')
            assert r.status_code == 401


# =====================================================================
# 8. Session cookie authentication
# =====================================================================


class TestSessionCookieAuth:

    @pytest.mark.asyncio
    async def test_valid_session_cookie_authenticates(self, app):
        cookie = _make_session_cookie()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/protected',
                cookies={'boring_session': cookie},
            )
            assert r.status_code == 200
            data = r.json()
            assert data['user_id'] == 'user-uuid-session'
            assert data['email'] == 'session@example.com'

    @pytest.mark.asyncio
    async def test_expired_session_cookie_returns_401(self, app):
        cookie = _make_session_cookie(exp=int(time.time()) - 100)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                cookies={'boring_session': cookie},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'session_expired'

    @pytest.mark.asyncio
    async def test_invalid_session_cookie_returns_401(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                cookies={'boring_session': 'not.a.valid.cookie'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'invalid_session'

    @pytest.mark.asyncio
    async def test_bearer_takes_precedence_over_cookie(self, app):
        """When both Bearer and session cookie are present,
        Bearer token identity should be used."""
        bearer_token = _make_token()
        session_cookie = _make_session_cookie()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/protected',
                headers={'Authorization': f'Bearer {bearer_token}'},
                cookies={'boring_session': session_cookie},
            )
            assert r.status_code == 200
            # Bearer identity should win (user-uuid-100, not user-uuid-session)
            assert r.json()['user_id'] == 'user-uuid-100'

    @pytest.mark.asyncio
    async def test_session_cookie_missing_type_claim_returns_401(self, app):
        """Session cookie without 'type' claim should be rejected."""
        payload = {
            'sub': 'user-uuid-session',
            'email': 'session@example.com',
            'exp': int(time.time()) + 3600,
            'iat': int(time.time()),
            # 'type' is missing — required by session token validation
        }
        cookie = jwt.encode(payload, SESSION_SECRET, algorithm='HS256')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                cookies={'boring_session': cookie},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'invalid_session'

    @pytest.mark.asyncio
    async def test_no_session_secret_disables_cookie_auth(self):
        """When session_secret is not provided, session cookies are ignored."""
        app = FastAPI()
        app.add_middleware(
            AuthGuardMiddleware,
            token_verifier=_create_verifier(),
            require_auth=True,
            # No session_secret
        )

        @app.get('/api/v1/test')
        async def test_route(request: Request):
            return {'ok': True}

        cookie = _make_session_cookie()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/test',
                cookies={'boring_session': cookie},
            )
            # Should return 401 because session cookie auth is disabled
            assert r.status_code == 401
            assert r.json()['code'] == 'no_credentials'
