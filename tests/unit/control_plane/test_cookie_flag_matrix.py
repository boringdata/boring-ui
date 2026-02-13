"""Cookie flag matrix tests across prod/dev modes.

Bead: bd-223o.7.2.1 (B2a)

Validates that session cookie security flags are correct by environment
and do not regress silently:
  - Production mode: HttpOnly=True, Secure=True, SameSite=Lax, Path=/
  - Local dev mode: HttpOnly=True, Secure=False, SameSite=Lax, Path=/
  - Cookie name is always 'boring_session'
  - Max-age matches config session_ttl
  - Domain is set when configured, absent when None
  - Flags are consistent across all cookie-setting paths:
    callback, rolling refresh, and logout (delete)
  - Custom redirect path does not affect cookie flags
  - Flag verification on both set-cookie and delete-cookie headers
"""

from __future__ import annotations

import re
import time

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from control_plane.app.routes.auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    SessionConfig,
    create_auth_router,
    create_session_token,
)
from control_plane.app.security.token_verify import (
    AuthIdentity,
    StaticKeyProvider,
    TokenVerifier,
)


# ── Shared fixtures ─────────────────────────────────────────────────

TEST_SUPABASE_SECRET = 'test-supabase-jwt-secret'
TEST_SESSION_SECRET = 'test-session-signing-secret'
TEST_AUDIENCE = 'authenticated'


def _make_supabase_token(**overrides) -> str:
    payload = {
        'sub': 'user-uuid-100',
        'email': 'cookie@test.com',
        'role': 'authenticated',
        'aud': TEST_AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    payload.update(overrides)
    return jwt.encode(payload, TEST_SUPABASE_SECRET, algorithm='HS256')


def _verifier():
    return TokenVerifier(
        key_provider=StaticKeyProvider(TEST_SUPABASE_SECRET),
        audience=TEST_AUDIENCE,
        algorithms=['HS256'],
    )


def _make_app(config: SessionConfig) -> FastAPI:
    app = FastAPI()
    router = create_auth_router(_verifier(), config)
    app.include_router(router)
    return app


def _parse_set_cookie(header: str) -> dict:
    """Parse a Set-Cookie header into a dict of attributes.

    Returns:
        Dict with keys like 'name', 'value', 'httponly' (bool),
        'secure' (bool), 'samesite' (str), 'max-age' (str),
        'path' (str), 'domain' (str or None).
    """
    parts = [p.strip() for p in header.split(';')]
    # First part is name=value.
    name_val = parts[0].split('=', 1)
    result = {
        'name': name_val[0].strip(),
        'value': name_val[1].strip() if len(name_val) > 1 else '',
        'httponly': False,
        'secure': False,
        'samesite': None,
        'max-age': None,
        'path': None,
        'domain': None,
    }
    for attr in parts[1:]:
        lower = attr.lower().strip()
        if lower == 'httponly':
            result['httponly'] = True
        elif lower == 'secure':
            result['secure'] = True
        elif lower.startswith('samesite='):
            result['samesite'] = attr.split('=', 1)[1].strip().lower()
        elif lower.startswith('max-age='):
            result['max-age'] = attr.split('=', 1)[1].strip()
        elif lower.startswith('path='):
            result['path'] = attr.split('=', 1)[1].strip()
        elif lower.startswith('domain='):
            result['domain'] = attr.split('=', 1)[1].strip()
    return result


async def _do_callback(app: FastAPI) -> dict:
    """Execute /auth/callback and return parsed Set-Cookie."""
    token = _make_supabase_token()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url='http://test',
        follow_redirects=False,
    ) as c:
        r = await c.get(f'/auth/callback?access_token={token}')
        assert r.status_code == 302
        raw = r.headers.get('set-cookie', '')
        return _parse_set_cookie(raw)


async def _do_rolling_refresh(app: FastAPI, config: SessionConfig) -> dict:
    """Execute /auth/session with near-expiry token and return parsed Set-Cookie."""
    # Create a session that expires soon (< 3600s threshold).
    short_config = SessionConfig(
        session_secret=config.session_secret,
        session_ttl=500,
    )
    identity = AuthIdentity(user_id='user-uuid-100', email='cookie@test.com')
    near_expiry = create_session_token(identity, short_config)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url='http://test',
    ) as c:
        r = await c.get(
            '/auth/session',
            cookies={SESSION_COOKIE_NAME: near_expiry},
        )
        assert r.status_code == 200
        raw = r.headers.get('set-cookie', '')
        return _parse_set_cookie(raw)


# =====================================================================
# 1. Production mode cookie flags
# =====================================================================


class TestProductionCookieFlags:
    """Production config: Secure=True, all security flags set."""

    @pytest.fixture
    def config(self):
        return SessionConfig(
            session_secret=TEST_SESSION_SECRET,
            cookie_secure=True,
            session_ttl=SESSION_TTL_SECONDS,
        )

    @pytest.fixture
    def app(self, config):
        return _make_app(config)

    @pytest.mark.asyncio
    async def test_callback_httponly(self, app):
        cookie = await _do_callback(app)
        assert cookie['httponly'] is True

    @pytest.mark.asyncio
    async def test_callback_secure(self, app):
        cookie = await _do_callback(app)
        assert cookie['secure'] is True

    @pytest.mark.asyncio
    async def test_callback_samesite_lax(self, app):
        cookie = await _do_callback(app)
        assert cookie['samesite'] == 'lax'

    @pytest.mark.asyncio
    async def test_callback_path_root(self, app):
        cookie = await _do_callback(app)
        assert cookie['path'] == '/'

    @pytest.mark.asyncio
    async def test_callback_max_age_matches_ttl(self, app):
        cookie = await _do_callback(app)
        assert cookie['max-age'] == str(SESSION_TTL_SECONDS)

    @pytest.mark.asyncio
    async def test_callback_cookie_name(self, app):
        cookie = await _do_callback(app)
        assert cookie['name'] == SESSION_COOKIE_NAME

    @pytest.mark.asyncio
    async def test_rolling_refresh_httponly(self, app, config):
        cookie = await _do_rolling_refresh(app, config)
        assert cookie['httponly'] is True

    @pytest.mark.asyncio
    async def test_rolling_refresh_secure(self, app, config):
        cookie = await _do_rolling_refresh(app, config)
        assert cookie['secure'] is True

    @pytest.mark.asyncio
    async def test_rolling_refresh_samesite_lax(self, app, config):
        cookie = await _do_rolling_refresh(app, config)
        assert cookie['samesite'] == 'lax'

    @pytest.mark.asyncio
    async def test_rolling_refresh_path_root(self, app, config):
        cookie = await _do_rolling_refresh(app, config)
        assert cookie['path'] == '/'


# =====================================================================
# 2. Local dev mode cookie flags
# =====================================================================


class TestLocalDevCookieFlags:
    """Local dev config: Secure=False, other security flags unchanged."""

    @pytest.fixture
    def config(self):
        return SessionConfig.for_local_dev(session_secret=TEST_SESSION_SECRET)

    @pytest.fixture
    def app(self, config):
        return _make_app(config)

    @pytest.mark.asyncio
    async def test_callback_httponly_still_true(self, app):
        cookie = await _do_callback(app)
        assert cookie['httponly'] is True

    @pytest.mark.asyncio
    async def test_callback_secure_false(self, app):
        cookie = await _do_callback(app)
        assert cookie['secure'] is False

    @pytest.mark.asyncio
    async def test_callback_samesite_still_lax(self, app):
        cookie = await _do_callback(app)
        assert cookie['samesite'] == 'lax'

    @pytest.mark.asyncio
    async def test_callback_path_still_root(self, app):
        cookie = await _do_callback(app)
        assert cookie['path'] == '/'

    @pytest.mark.asyncio
    async def test_rolling_refresh_secure_false(self, app, config):
        cookie = await _do_rolling_refresh(app, config)
        assert cookie['secure'] is False

    @pytest.mark.asyncio
    async def test_rolling_refresh_httponly_still_true(self, app, config):
        cookie = await _do_rolling_refresh(app, config)
        assert cookie['httponly'] is True


# =====================================================================
# 3. Domain configuration
# =====================================================================


class TestDomainConfiguration:
    """Cookie domain is set when configured, absent when None."""

    @pytest.mark.asyncio
    async def test_domain_set_when_configured(self):
        config = SessionConfig(
            session_secret=TEST_SESSION_SECRET,
            cookie_domain='.example.com',
        )
        app = _make_app(config)
        cookie = await _do_callback(app)
        assert cookie['domain'] == '.example.com'

    @pytest.mark.asyncio
    async def test_domain_absent_when_none(self):
        config = SessionConfig(
            session_secret=TEST_SESSION_SECRET,
            cookie_domain=None,
        )
        app = _make_app(config)
        cookie = await _do_callback(app)
        # Domain should either be None or not present in header.
        assert cookie['domain'] is None

    @pytest.mark.asyncio
    async def test_domain_on_rolling_refresh(self):
        config = SessionConfig(
            session_secret=TEST_SESSION_SECRET,
            cookie_domain='.app.dev',
        )
        app = _make_app(config)
        cookie = await _do_rolling_refresh(app, config)
        assert cookie['domain'] == '.app.dev'


# =====================================================================
# 4. Custom session TTL
# =====================================================================


class TestCustomSessionTTL:
    """max-age tracks session_ttl config across modes."""

    @pytest.mark.asyncio
    async def test_custom_ttl_in_callback(self):
        config = SessionConfig(
            session_secret=TEST_SESSION_SECRET,
            session_ttl=7200,
        )
        app = _make_app(config)
        cookie = await _do_callback(app)
        assert cookie['max-age'] == '7200'

    @pytest.mark.asyncio
    async def test_default_ttl_is_24_hours(self):
        config = SessionConfig(session_secret=TEST_SESSION_SECRET)
        app = _make_app(config)
        cookie = await _do_callback(app)
        assert cookie['max-age'] == str(3600 * 24)


# =====================================================================
# 5. Logout cookie deletion
# =====================================================================


class TestLogoutCookieDeletion:
    """Logout clears the session cookie with correct name and path."""

    @pytest.mark.asyncio
    async def test_logout_deletes_correct_cookie_name(self):
        config = SessionConfig(session_secret=TEST_SESSION_SECRET)
        app = _make_app(config)
        identity = AuthIdentity(user_id='u1', email='e@x.com')
        session_token = create_session_token(identity, config)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.post(
                '/auth/logout',
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            raw = r.headers.get('set-cookie', '')
            # Delete-cookie sets max-age=0 or expires in the past.
            assert SESSION_COOKIE_NAME in raw
            # Path should still be '/'.
            parsed = _parse_set_cookie(raw)
            assert parsed['path'] == '/'

    @pytest.mark.asyncio
    async def test_logout_max_age_is_zero(self):
        config = SessionConfig(session_secret=TEST_SESSION_SECRET)
        app = _make_app(config)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.post('/auth/logout')
            raw = r.headers.get('set-cookie', '')
            parsed = _parse_set_cookie(raw)
            assert parsed['max-age'] == '0'


# =====================================================================
# 6. Custom redirect does not affect cookie flags
# =====================================================================


class TestRedirectDoesNotAffectCookies:
    """Custom redirect_path changes Location header but not cookie flags."""

    @pytest.mark.asyncio
    async def test_custom_redirect_preserves_flags(self):
        config = SessionConfig(
            session_secret=TEST_SESSION_SECRET,
            cookie_secure=True,
            redirect_path='/dashboard/home',
        )
        app = _make_app(config)
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            assert r.status_code == 302
            assert r.headers['location'] == '/dashboard/home'
            cookie = _parse_set_cookie(r.headers.get('set-cookie', ''))
            assert cookie['httponly'] is True
            assert cookie['secure'] is True
            assert cookie['samesite'] == 'lax'


# =====================================================================
# 7. SessionConfig.for_local_dev defaults
# =====================================================================


class TestLocalDevConfigDefaults:
    """Verify for_local_dev() factory produces correct defaults."""

    def test_secure_is_false(self):
        config = SessionConfig.for_local_dev()
        assert config.cookie_secure is False

    def test_ttl_is_default(self):
        config = SessionConfig.for_local_dev()
        assert config.session_ttl == SESSION_TTL_SECONDS

    def test_secret_auto_generated(self):
        c1 = SessionConfig.for_local_dev()
        c2 = SessionConfig.for_local_dev()
        assert len(c1.session_secret) > 16
        # Two calls produce distinct secrets.
        assert c1.session_secret != c2.session_secret

    def test_explicit_secret_honored(self):
        config = SessionConfig.for_local_dev(session_secret='my-dev-secret')
        assert config.session_secret == 'my-dev-secret'

    def test_domain_is_none(self):
        config = SessionConfig.for_local_dev()
        assert config.cookie_domain is None

    def test_redirect_path_is_default(self):
        config = SessionConfig.for_local_dev()
        assert config.redirect_path == '/'


# =====================================================================
# 8. Cookie name constant
# =====================================================================


class TestCookieNameConstant:
    """Cookie name is stable and documented."""

    def test_cookie_name_is_boring_session(self):
        assert SESSION_COOKIE_NAME == 'boring_session'

    def test_default_ttl_constant(self):
        assert SESSION_TTL_SECONDS == 86400
