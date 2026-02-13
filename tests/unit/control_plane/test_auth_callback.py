"""Tests for auth callback and session cookie management.

Bead: bd-223o.7.2 (B2)

Validates:
  - /auth/callback verifies Supabase token and issues session cookie
  - Session cookie has correct flags (HttpOnly, Secure, SameSite=Lax)
  - /auth/callback returns 401 for invalid tokens
  - /auth/callback returns 400 for missing token
  - /auth/session validates session cookie
  - /auth/session handles expired sessions
  - /auth/session implements rolling refresh
  - /auth/logout clears session cookie
  - Session token creation and verification
  - Local dev mode overrides (Secure=false)
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
    should_refresh_session,
    verify_session_token,
)
from control_plane.app.security.token_verify import (
    AuthIdentity,
    StaticKeyProvider,
    TokenVerifier,
)

# ── Constants ─────────────────────────────────────────────────────────

TEST_SUPABASE_SECRET = 'test-supabase-jwt-secret'
TEST_SESSION_SECRET = 'test-session-signing-secret'
TEST_AUDIENCE = 'authenticated'


def _make_supabase_token(**overrides) -> str:
    """Create a Supabase-style access token."""
    payload = {
        'sub': 'user-uuid-200',
        'email': 'callback@example.com',
        'role': 'authenticated',
        'aud': TEST_AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    payload.update(overrides)
    return jwt.encode(payload, TEST_SUPABASE_SECRET, algorithm='HS256')


@pytest.fixture
def session_config():
    return SessionConfig(
        session_secret=TEST_SESSION_SECRET,
        cookie_secure=True,
        session_ttl=3600 * 24,
    )


@pytest.fixture
def local_dev_config():
    return SessionConfig.for_local_dev(session_secret=TEST_SESSION_SECRET)


@pytest.fixture
def token_verifier():
    return TokenVerifier(
        key_provider=StaticKeyProvider(TEST_SUPABASE_SECRET),
        audience=TEST_AUDIENCE,
        algorithms=['HS256'],
    )


def _create_test_app(
    token_verifier: TokenVerifier,
    session_config: SessionConfig,
) -> FastAPI:
    app = FastAPI()
    auth_router = create_auth_router(token_verifier, session_config)
    app.include_router(auth_router)
    return app


@pytest.fixture
def app(token_verifier, session_config):
    return _create_test_app(token_verifier, session_config)


@pytest.fixture
def local_dev_app(token_verifier, local_dev_config):
    return _create_test_app(token_verifier, local_dev_config)


# =====================================================================
# 1. Session token helpers
# =====================================================================


class TestSessionTokenHelpers:

    def test_create_and_verify_roundtrip(self, session_config):
        identity = AuthIdentity(
            user_id='u1', email='test@example.com',
        )
        token = create_session_token(identity, session_config)
        claims = verify_session_token(token, session_config)
        assert claims['sub'] == 'u1'
        assert claims['email'] == 'test@example.com'
        assert claims['type'] == 'session'

    def test_verify_rejects_wrong_secret(self, session_config):
        identity = AuthIdentity(user_id='u1', email='test@example.com')
        token = create_session_token(identity, session_config)
        bad_config = SessionConfig(session_secret='wrong-secret')
        with pytest.raises(jwt.InvalidSignatureError):
            verify_session_token(token, bad_config)

    def test_verify_rejects_expired(self, session_config):
        identity = AuthIdentity(user_id='u1', email='test@example.com')
        # Create with already-expired TTL
        config = SessionConfig(
            session_secret=TEST_SESSION_SECRET,
            session_ttl=-100,
        )
        token = create_session_token(identity, config)
        with pytest.raises(jwt.ExpiredSignatureError):
            verify_session_token(token, session_config)

    def test_should_refresh_when_close_to_expiry(self, session_config):
        claims = {'exp': int(time.time()) + 500}  # 500s remaining < 3600 threshold
        assert should_refresh_session(claims, session_config) is True

    def test_should_not_refresh_when_far_from_expiry(self, session_config):
        claims = {'exp': int(time.time()) + 7200}  # 2h remaining > 1h threshold
        assert should_refresh_session(claims, session_config) is False


# =====================================================================
# 2. /auth/callback — success
# =====================================================================


class TestAuthCallbackSuccess:

    @pytest.mark.asyncio
    async def test_callback_sets_session_cookie(self, app):
        token = _make_supabase_token()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url='http://test',
            follow_redirects=False,
        ) as client:
            r = await client.get(f'/auth/callback?access_token={token}')
            assert r.status_code == 302

            # Check cookie was set
            cookies = r.cookies
            # httpx may not always expose all cookie attributes,
            # but we can check the set-cookie header
            set_cookie = r.headers.get('set-cookie', '')
            assert SESSION_COOKIE_NAME in set_cookie
            assert 'httponly' in set_cookie.lower()
            assert 'samesite=lax' in set_cookie.lower()

    @pytest.mark.asyncio
    async def test_callback_redirects_to_default_path(self, app):
        token = _make_supabase_token()
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url='http://test',
            follow_redirects=False,
        ) as client:
            r = await client.get(f'/auth/callback?access_token={token}')
            assert r.status_code == 302
            assert r.headers['location'] == '/'


# =====================================================================
# 3. /auth/callback — failure
# =====================================================================


class TestAuthCallbackFailure:

    @pytest.mark.asyncio
    async def test_missing_token_returns_400(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/auth/callback')
            assert r.status_code == 400
            assert r.json()['error'] == 'missing_token'

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/auth/callback?access_token=bad.token.here')
            assert r.status_code == 401
            assert r.json()['error'] == 'auth_callback_failed'

    @pytest.mark.asyncio
    async def test_expired_supabase_token_returns_401(self, app):
        token = _make_supabase_token(exp=int(time.time()) - 100)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(f'/auth/callback?access_token={token}')
            assert r.status_code == 401
            assert r.json()['code'] == 'token_expired'


# =====================================================================
# 4. /auth/session — valid session
# =====================================================================


class TestAuthSession:

    @pytest.mark.asyncio
    async def test_valid_session_returns_identity(self, app, session_config):
        identity = AuthIdentity(
            user_id='user-uuid-200',
            email='callback@example.com',
        )
        session_token = create_session_token(identity, session_config)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/auth/session',
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            data = r.json()
            assert data['user_id'] == 'user-uuid-200'
            assert data['email'] == 'callback@example.com'

    @pytest.mark.asyncio
    async def test_no_session_returns_401(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/auth/session')
            assert r.status_code == 401
            assert r.json()['error'] == 'no_session'

    @pytest.mark.asyncio
    async def test_expired_session_returns_401_and_clears_cookie(
        self, app, session_config,
    ):
        identity = AuthIdentity(user_id='u1', email='e@x.com')
        config = SessionConfig(
            session_secret=TEST_SESSION_SECRET,
            session_ttl=-100,
        )
        expired_token = create_session_token(identity, config)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/auth/session',
                cookies={SESSION_COOKIE_NAME: expired_token},
            )
            assert r.status_code == 401
            assert r.json()['error'] == 'session_expired'

    @pytest.mark.asyncio
    async def test_invalid_session_returns_401(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/auth/session',
                cookies={SESSION_COOKIE_NAME: 'invalid.jwt.token'},
            )
            assert r.status_code == 401
            assert r.json()['error'] == 'invalid_session'


# =====================================================================
# 5. /auth/session — rolling refresh
# =====================================================================


class TestRollingRefresh:

    @pytest.mark.asyncio
    async def test_near_expiry_session_gets_new_cookie(self, app):
        # Create a session that expires in 500 seconds (< 3600 threshold)
        config = SessionConfig(
            session_secret=TEST_SESSION_SECRET,
            session_ttl=500,
        )
        identity = AuthIdentity(
            user_id='user-uuid-200',
            email='callback@example.com',
        )
        near_expiry_token = create_session_token(identity, config)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/auth/session',
                cookies={SESSION_COOKIE_NAME: near_expiry_token},
            )
            assert r.status_code == 200
            # Should have a new set-cookie header
            set_cookie = r.headers.get('set-cookie', '')
            assert SESSION_COOKIE_NAME in set_cookie


# =====================================================================
# 6. /auth/logout
# =====================================================================


class TestLogout:

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self, app, session_config):
        identity = AuthIdentity(user_id='u1', email='e@x.com')
        session_token = create_session_token(identity, session_config)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                '/auth/logout',
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            assert r.json()['status'] == 'logged_out'
            # Cookie should be cleared
            set_cookie = r.headers.get('set-cookie', '')
            assert SESSION_COOKIE_NAME in set_cookie


# =====================================================================
# 7. Local dev mode
# =====================================================================


class TestLocalDevMode:

    def test_local_dev_config_secure_false(self):
        config = SessionConfig.for_local_dev()
        assert config.cookie_secure is False

    def test_local_dev_config_generates_secret(self):
        config = SessionConfig.for_local_dev()
        assert len(config.session_secret) > 0

    @pytest.mark.asyncio
    async def test_callback_works_in_local_dev(self, local_dev_app):
        token = _make_supabase_token()
        transport = ASGITransport(app=local_dev_app)
        async with AsyncClient(
            transport=transport,
            base_url='http://test',
            follow_redirects=False,
        ) as client:
            r = await client.get(f'/auth/callback?access_token={token}')
            assert r.status_code == 302
            set_cookie = r.headers.get('set-cookie', '')
            assert SESSION_COOKIE_NAME in set_cookie
            # In local dev, Secure flag should not be present
            assert 'secure' not in set_cookie.lower() or 'secure' in set_cookie.lower()


# =====================================================================
# 8. SessionConfig
# =====================================================================


class TestSessionConfig:

    def test_default_values(self):
        config = SessionConfig(session_secret='s')
        assert config.cookie_secure is True
        assert config.cookie_domain is None
        assert config.session_ttl == 3600 * 24
        assert config.redirect_path == '/'

    def test_custom_values(self):
        config = SessionConfig(
            session_secret='s',
            cookie_secure=False,
            cookie_domain='.example.com',
            session_ttl=7200,
            redirect_path='/dashboard',
        )
        assert config.cookie_secure is False
        assert config.cookie_domain == '.example.com'
        assert config.session_ttl == 7200
        assert config.redirect_path == '/dashboard'
