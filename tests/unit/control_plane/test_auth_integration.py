"""Integration tests for auth success and 401 failure paths.

Bead: bd-223o.7.3.1 (B3a)

Covers happy-path login → /api/v1/me plus invalid/expired credential paths
with deterministic expected error codes:
  - Bearer token → /api/v1/me success returns user identity
  - Session cookie → /api/v1/me success returns same identity shape
  - Missing credentials → 401 no_credentials
  - Invalid Bearer token → 401 with verification error code
  - Expired Bearer token → 401 token_expired
  - Invalid session cookie → 401 invalid_session
  - Expired session cookie → 401 session_expired
  - Exempt paths pass through without auth
  - Full callback → session → /me round-trip
  - Auth transport precedence: Bearer > session cookie
"""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from control_plane.app.routes.auth import (
    SESSION_COOKIE_NAME,
    SessionConfig,
    create_auth_router,
    create_session_token,
)
from control_plane.app.routes.me import router as me_router
from control_plane.app.security.auth_guard import AuthGuardMiddleware
from control_plane.app.security.token_verify import (
    AuthIdentity,
    StaticKeyProvider,
    TokenVerifier,
)


# ── Shared constants ────────────────────────────────────────────────

SUPABASE_SECRET = 'test-supabase-secret-for-integration'
SESSION_SECRET = 'test-session-secret-for-integration'
AUDIENCE = 'authenticated'


def _make_supabase_token(**overrides) -> str:
    payload = {
        'sub': 'user-int-001',
        'email': 'integration@test.com',
        'role': 'authenticated',
        'aud': AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    payload.update(overrides)
    return jwt.encode(payload, SUPABASE_SECRET, algorithm='HS256')


def _verifier():
    return TokenVerifier(
        key_provider=StaticKeyProvider(SUPABASE_SECRET),
        audience=AUDIENCE,
        algorithms=['HS256'],
    )


def _session_config():
    return SessionConfig(
        session_secret=SESSION_SECRET,
        cookie_secure=False,
    )


def _build_app() -> FastAPI:
    """Build a complete app with auth guard, auth routes, and /me."""
    app = FastAPI()
    verifier = _verifier()
    config = _session_config()

    # Auth routes (callback, session, logout).
    auth_router = create_auth_router(verifier, config)
    app.include_router(auth_router)

    # Protected /api/v1/me route.
    app.include_router(me_router)

    # Auth guard middleware — must be added AFTER routers.
    app.add_middleware(
        AuthGuardMiddleware,
        token_verifier=verifier,
        session_secret=SESSION_SECRET,
    )

    return app


@pytest.fixture
def app():
    return _build_app()


# =====================================================================
# 1. Happy path: Bearer → /api/v1/me
# =====================================================================


class TestBearerHappyPath:
    """Bearer token authenticates to /api/v1/me successfully."""

    @pytest.mark.asyncio
    async def test_valid_bearer_returns_identity(self, app):
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 200
            data = r.json()
            assert data['user_id'] == 'user-int-001'
            assert data['email'] == 'integration@test.com'
            assert data['role'] == 'authenticated'

    @pytest.mark.asyncio
    async def test_response_shape(self, app):
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert set(r.json().keys()) == {'user_id', 'email', 'role'}


# =====================================================================
# 2. Happy path: Session cookie → /api/v1/me
# =====================================================================


class TestSessionCookieHappyPath:
    """Session cookie authenticates to /api/v1/me successfully."""

    @pytest.mark.asyncio
    async def test_valid_session_returns_identity(self, app):
        identity = AuthIdentity(
            user_id='user-int-001',
            email='integration@test.com',
        )
        session_token = create_session_token(identity, _session_config())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            data = r.json()
            assert data['user_id'] == 'user-int-001'
            assert data['email'] == 'integration@test.com'


# =====================================================================
# 3. Missing credentials → 401
# =====================================================================


class TestMissingCredentials:
    """No auth header and no session cookie returns 401."""

    @pytest.mark.asyncio
    async def test_no_credentials_returns_401(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/api/v1/me')
            assert r.status_code == 401
            body = r.json()
            assert body['error'] == 'unauthorized'
            assert body['code'] == 'no_credentials'

    @pytest.mark.asyncio
    async def test_www_authenticate_header_present(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/api/v1/me')
            assert r.status_code == 401
            assert 'bearer' in r.headers.get('www-authenticate', '').lower()


# =====================================================================
# 4. Invalid Bearer token → 401
# =====================================================================


class TestInvalidBearerToken:
    """Malformed or wrong-secret Bearer tokens return 401."""

    @pytest.mark.asyncio
    async def test_garbage_token(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': 'Bearer garbage.token.here'},
            )
            assert r.status_code == 401
            body = r.json()
            assert body['error'] == 'unauthorized'
            assert body['code'] in ('decode_error', 'invalid_token')

    @pytest.mark.asyncio
    async def test_wrong_secret_token(self, app):
        token = jwt.encode(
            {
                'sub': 'user-1',
                'email': 'e@x.com',
                'aud': AUDIENCE,
                'exp': int(time.time()) + 3600,
            },
            'wrong-secret',
            algorithm='HS256',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'decode_error'

    @pytest.mark.asyncio
    async def test_wrong_audience_token(self, app):
        token = _make_supabase_token(aud='wrong-audience')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'invalid_audience'


# =====================================================================
# 5. Expired Bearer token → 401
# =====================================================================


class TestExpiredBearerToken:
    """Expired Bearer tokens return 401 token_expired."""

    @pytest.mark.asyncio
    async def test_expired_bearer_returns_401(self, app):
        token = _make_supabase_token(exp=int(time.time()) - 100)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'token_expired'

    @pytest.mark.asyncio
    async def test_expired_bearer_has_www_authenticate(self, app):
        token = _make_supabase_token(exp=int(time.time()) - 100)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert 'bearer' in r.headers.get('www-authenticate', '').lower()


# =====================================================================
# 6. Invalid session cookie → 401
# =====================================================================


class TestInvalidSessionCookie:
    """Invalid session cookies return 401 invalid_session."""

    @pytest.mark.asyncio
    async def test_garbage_session_cookie(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: 'not.valid.jwt'},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'invalid_session'

    @pytest.mark.asyncio
    async def test_wrong_secret_session_cookie(self, app):
        # Session signed with wrong secret.
        payload = {
            'sub': 'user-1',
            'email': 'e@x.com',
            'exp': int(time.time()) + 3600,
            'type': 'session',
        }
        bad_token = jwt.encode(payload, 'wrong-session-secret', algorithm='HS256')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: bad_token},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'invalid_session'


# =====================================================================
# 7. Expired session cookie → 401
# =====================================================================


class TestExpiredSessionCookie:
    """Expired session cookies return 401 session_expired."""

    @pytest.mark.asyncio
    async def test_expired_session_returns_401(self, app):
        identity = AuthIdentity(user_id='user-1', email='e@x.com')
        config = SessionConfig(session_secret=SESSION_SECRET, session_ttl=-100)
        expired_token = create_session_token(identity, config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: expired_token},
            )
            assert r.status_code == 401
            assert r.json()['code'] == 'session_expired'


# =====================================================================
# 8. Exempt paths pass through
# =====================================================================


class TestExemptPaths:
    """Exempt paths do not require authentication."""

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, app):
        # /health should work without any credentials.
        # Add a health route for this test.
        @app.get('/health')
        async def health():
            return {'status': 'ok'}

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/health')
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_callback_no_auth_required(self, app):
        # /auth/callback is exempt — returns 400 for missing token, not 401.
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/auth/callback')
            assert r.status_code == 400
            assert r.json()['error'] == 'missing_token'


# =====================================================================
# 9. Full callback → session → /me round-trip
# =====================================================================


class TestFullRoundTrip:
    """Complete auth flow: callback → session cookie → /api/v1/me."""

    @pytest.mark.asyncio
    async def test_callback_sets_cookie_then_me_works(self, app):
        supabase_token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            # Step 1: Auth callback — sets session cookie.
            cb = await c.get(f'/auth/callback?access_token={supabase_token}')
            assert cb.status_code == 302

            # Extract the session cookie from Set-Cookie header.
            set_cookie = cb.headers.get('set-cookie', '')
            assert SESSION_COOKIE_NAME in set_cookie
            # Parse session token from the cookie.
            import re
            match = re.search(
                rf'{SESSION_COOKIE_NAME}=([^;]+)', set_cookie,
            )
            assert match is not None
            session_token = match.group(1)

            # Step 2: Use session cookie to access /api/v1/me.
            r = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            data = r.json()
            assert data['user_id'] == 'user-int-001'
            assert data['email'] == 'integration@test.com'


# =====================================================================
# 10. Transport precedence: Bearer > session cookie
# =====================================================================


class TestTransportPrecedence:
    """When both Bearer and session cookie present, Bearer wins."""

    @pytest.mark.asyncio
    async def test_bearer_wins_over_session(self, app):
        # Bearer token for user-bearer.
        bearer_token = _make_supabase_token(
            sub='user-bearer', email='bearer@test.com',
        )
        # Session cookie for user-session.
        identity = AuthIdentity(
            user_id='user-session', email='session@test.com',
        )
        session_token = create_session_token(identity, _session_config())

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': f'Bearer {bearer_token}'},
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            # Bearer identity should win.
            assert r.json()['user_id'] == 'user-bearer'
            assert r.json()['email'] == 'bearer@test.com'


# =====================================================================
# 11. Error response structure consistency
# =====================================================================


class TestErrorResponseStructure:
    """All 401 responses have consistent error/code/detail keys."""

    @pytest.mark.asyncio
    async def test_no_credentials_error_structure(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/api/v1/me')
            body = r.json()
            assert set(body.keys()) == {'error', 'code', 'detail'}

    @pytest.mark.asyncio
    async def test_invalid_bearer_error_structure(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'Authorization': 'Bearer bad.token'},
            )
            body = r.json()
            assert 'error' in body
            assert 'code' in body

    @pytest.mark.asyncio
    async def test_expired_session_error_structure(self, app):
        identity = AuthIdentity(user_id='u', email='e@x.com')
        config = SessionConfig(session_secret=SESSION_SECRET, session_ttl=-100)
        expired = create_session_token(identity, config)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: expired},
            )
            body = r.json()
            assert body['error'] == 'unauthorized'
            assert body['code'] == 'session_expired'
            assert 'detail' in body
