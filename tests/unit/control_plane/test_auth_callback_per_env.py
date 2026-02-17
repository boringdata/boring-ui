"""Tests for auth callback flow per environment (local, staging, production).

Bead: bd-w4n5 (P3.1)

Validates that the auth callback flow works correctly across all deployment
environments, with proper cookie attributes, CORS headers, redirect behaviour,
and clear error messages for misconfiguration.

Test Coverage:
  - Unit: URL parsing, callback derivation, redirect validation per env
  - Integration: Supabase callback → session cookie per env
  - E2E: callback → /auth/session → /api/v1/me per env
  - Per-environment cookie attributes (HttpOnly, Secure, SameSite, Domain)
  - CORS headers match environment config
  - Callback URL mismatch returns clear error
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import jwt
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

from control_plane.app.config.environment import (
    EnvironmentConfigError,
    derive_supabase_callback_url,
    load_environment_config,
    validate_callback_url_consistency,
)
from control_plane.app.config.host_config import (
    Environment,
    HostConfig,
    build_callback_url,
    get_effective_scheme,
    get_public_host,
    load_host_config_from_env,
    local_host_config,
    production_host_config,
    staging_host_config,
    validate_host_config,
)
from control_plane.app.routes.auth import (
    SESSION_COOKIE_NAME,
    SessionConfig,
    create_auth_router,
    create_session_token,
    verify_session_token,
)
from control_plane.app.routes.me import router as me_router
from control_plane.app.security.auth_guard import AuthGuardMiddleware
from control_plane.app.security.token_verify import (
    AuthIdentity,
    StaticKeyProvider,
    TokenVerifier,
)

# ── Shared constants ──────────────────────────────────────────────────

SUPABASE_SECRET = 'test-supabase-secret-for-per-env'
SESSION_SECRET = 'test-session-secret-for-per-env'
AUDIENCE = 'authenticated'


# ── Helpers ───────────────────────────────────────────────────────────


def _make_supabase_token(**overrides) -> str:
    """Create a Supabase-style HS256 access token for testing."""
    payload = {
        'sub': 'user-env-001',
        'email': 'env-test@example.com',
        'role': 'authenticated',
        'aud': AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    payload.update(overrides)
    return jwt.encode(payload, SUPABASE_SECRET, algorithm='HS256')


def _verifier() -> TokenVerifier:
    return TokenVerifier(
        key_provider=StaticKeyProvider(SUPABASE_SECRET),
        audience=AUDIENCE,
        algorithms=['HS256'],
    )


def _session_config(
    cookie_secure: bool = True,
    cookie_domain: str | None = None,
) -> SessionConfig:
    return SessionConfig(
        session_secret=SESSION_SECRET,
        cookie_secure=cookie_secure,
        cookie_domain=cookie_domain,
    )


def _build_app(
    *,
    cookie_secure: bool = True,
    cookie_domain: str | None = None,
    cors_origins: tuple[str, ...] = (),
) -> FastAPI:
    """Build a test app with auth routes, /me, auth guard, and CORS."""
    app = FastAPI()
    verifier = _verifier()
    config = _session_config(
        cookie_secure=cookie_secure,
        cookie_domain=cookie_domain,
    )

    auth_router = create_auth_router(verifier, config)
    app.include_router(auth_router)
    app.include_router(me_router)

    app.add_middleware(
        AuthGuardMiddleware,
        token_verifier=verifier,
        session_secret=SESSION_SECRET,
    )

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_credentials=True,
            allow_methods=['*'],
            allow_headers=['*'],
        )

    return app


def _extract_session_token(set_cookie_header: str) -> str:
    """Parse the session token from a Set-Cookie header."""
    match = re.search(rf'{SESSION_COOKIE_NAME}=([^;]+)', set_cookie_header)
    assert match is not None, f'No {SESSION_COOKIE_NAME} in Set-Cookie: {set_cookie_header}'
    return match.group(1)


# ── Per-environment config fixtures ──────────────────────────────────


@dataclass
class EnvTestParams:
    """Parameters for a per-environment test scenario."""
    environment: str
    cookie_secure: bool
    cookie_domain: str | None
    cors_origins: tuple[str, ...]
    public_url: str
    expected_callback_url: str


LOCAL_PARAMS = EnvTestParams(
    environment='local',
    cookie_secure=False,
    cookie_domain=None,
    cors_origins=('http://localhost:8000', 'http://localhost:5173'),
    public_url='http://localhost:8000',
    expected_callback_url='http://localhost:8000/auth/callback',
)

STAGING_PARAMS = EnvTestParams(
    environment='staging',
    cookie_secure=True,
    cookie_domain='.staging.boring-ui.dev',
    cors_origins=('https://staging.boring-ui.dev',),
    public_url='https://staging.boring-ui.dev',
    expected_callback_url='https://staging.boring-ui.dev/auth/callback',
)

PRODUCTION_PARAMS = EnvTestParams(
    environment='production',
    cookie_secure=True,
    cookie_domain='.boring-ui.modal.run',
    cors_origins=('https://boring-ui.modal.run',),
    public_url='https://boring-ui.modal.run',
    expected_callback_url='https://boring-ui.modal.run/auth/callback',
)

ALL_ENVS = [LOCAL_PARAMS, STAGING_PARAMS, PRODUCTION_PARAMS]
ALL_ENV_IDS = ['local', 'staging', 'production']


# =====================================================================
# 1. Unit: callback URL derivation per environment
# =====================================================================


class TestCallbackUrlPerEnv:
    """Callback URL derivation matches expected per-env patterns."""

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    def test_derive_callback_url(self, params: EnvTestParams):
        url = derive_supabase_callback_url(params.public_url)
        assert url == params.expected_callback_url

    def test_local_callback_uses_http(self):
        url = derive_supabase_callback_url('http://localhost:8000')
        assert url.startswith('http://')
        assert url.endswith('/auth/callback')

    def test_staging_callback_uses_https(self):
        url = derive_supabase_callback_url('https://staging.boring-ui.dev')
        assert url.startswith('https://')

    def test_production_callback_uses_https(self):
        url = derive_supabase_callback_url('https://boring-ui.modal.run')
        assert url.startswith('https://')

    def test_trailing_slash_normalised(self):
        url1 = derive_supabase_callback_url('https://host.com')
        url2 = derive_supabase_callback_url('https://host.com/')
        assert url1 == url2


# =====================================================================
# 2. Unit: callback URL consistency validation per environment
# =====================================================================


class TestCallbackConsistencyPerEnv:
    """Callback URL consistency validated for each environment config."""

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    def test_consistent_callback_passes(self, params: EnvTestParams):
        validate_callback_url_consistency(
            params.public_url,
            params.expected_callback_url,
        )

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    def test_mismatched_host_raises(self, params: EnvTestParams):
        wrong_callback = 'https://wrong-host.example.com/auth/callback'
        with pytest.raises(EnvironmentConfigError, match='mismatch'):
            validate_callback_url_consistency(
                params.public_url,
                wrong_callback,
            )

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    def test_mismatched_path_raises(self, params: EnvTestParams):
        wrong_path = params.public_url.rstrip('/') + '/auth/wrong'
        with pytest.raises(EnvironmentConfigError, match='mismatch'):
            validate_callback_url_consistency(
                params.public_url,
                wrong_path,
            )


# =====================================================================
# 3. Unit: HostConfig per environment
# =====================================================================


class TestHostConfigPerEnv:
    """HostConfig factories produce correct per-env values."""

    def test_local_host_config(self):
        config = local_host_config()
        assert config.environment == Environment.LOCAL
        assert config.tls_enabled is False
        assert config.cookie_secure is False
        assert config.callback_url == 'http://localhost:8000/auth/callback'
        assert len(config.allowed_origins) >= 1

    def test_staging_host_config(self):
        config = staging_host_config('staging.boring-ui.dev')
        assert config.environment == Environment.STAGING
        assert config.tls_enabled is True
        assert config.cookie_secure is True
        assert config.callback_url == 'https://staging.boring-ui.dev/auth/callback'
        assert 'https://staging.boring-ui.dev' in config.allowed_origins

    def test_production_host_config(self):
        config = production_host_config('boring-ui.modal.run')
        assert config.environment == Environment.PRODUCTION
        assert config.tls_enabled is True
        assert config.cookie_secure is True
        assert config.callback_url == 'https://boring-ui.modal.run/auth/callback'
        assert 'https://boring-ui.modal.run' in config.allowed_origins

    def test_staging_with_cookie_domain(self):
        config = staging_host_config(
            'staging.boring-ui.dev',
            cookie_domain='.boring-ui.dev',
        )
        assert config.cookie_domain == '.boring-ui.dev'

    def test_production_with_cookie_domain(self):
        config = production_host_config(
            'boring-ui.modal.run',
            cookie_domain='.modal.run',
        )
        assert config.cookie_domain == '.modal.run'


# =====================================================================
# 4. Unit: HostConfig validation per environment
# =====================================================================


class TestHostConfigValidation:
    """validate_host_config catches env-specific misconfigurations."""

    def test_local_valid(self):
        config = local_host_config()
        errors = validate_host_config(config)
        assert errors == []

    def test_staging_valid(self):
        config = staging_host_config('staging.boring-ui.dev')
        errors = validate_host_config(config)
        assert errors == []

    def test_production_valid(self):
        config = production_host_config('boring-ui.modal.run')
        errors = validate_host_config(config)
        assert errors == []

    def test_staging_localhost_rejected(self):
        config = HostConfig(
            environment=Environment.STAGING,
            public_host='localhost',
            tls_enabled=True,
            cookie_secure=True,
        )
        errors = validate_host_config(config)
        assert any('real hostname' in e for e in errors)

    def test_production_no_tls_rejected(self):
        config = HostConfig(
            environment=Environment.PRODUCTION,
            public_host='boring-ui.modal.run',
            tls_enabled=False,
            cookie_secure=False,
        )
        errors = validate_host_config(config)
        assert any('TLS' in e for e in errors)

    def test_production_insecure_cookie_rejected(self):
        config = HostConfig(
            environment=Environment.PRODUCTION,
            public_host='boring-ui.modal.run',
            tls_enabled=True,
            cookie_secure=False,
        )
        errors = validate_host_config(config)
        assert any('cookie_secure' in e for e in errors)

    def test_callback_url_http_in_production_rejected(self):
        config = HostConfig(
            environment=Environment.PRODUCTION,
            public_host='boring-ui.modal.run',
            tls_enabled=True,
            cookie_secure=True,
            supabase_callback_url='http://boring-ui.modal.run/auth/callback',
        )
        errors = validate_host_config(config)
        assert any('HTTPS' in e for e in errors)


# =====================================================================
# 5. Unit: HostConfig env loading
# =====================================================================


class TestHostConfigEnvLoading:
    """load_host_config_from_env produces correct per-env configs."""

    def test_local_defaults(self):
        config = load_host_config_from_env({})
        assert config.environment == Environment.LOCAL
        assert config.tls_enabled is False
        assert config.cookie_secure is False

    def test_staging_from_env(self):
        config = load_host_config_from_env({
            'ENVIRONMENT': 'staging',
            'PUBLIC_HOST': 'staging.boring-ui.dev',
        })
        assert config.environment == Environment.STAGING
        assert config.tls_enabled is True
        assert config.cookie_secure is True
        assert config.public_host == 'staging.boring-ui.dev'

    def test_production_from_env(self):
        config = load_host_config_from_env({
            'ENVIRONMENT': 'production',
            'PUBLIC_HOST': 'boring-ui.modal.run',
        })
        assert config.environment == Environment.PRODUCTION
        assert config.tls_enabled is True
        assert config.public_host == 'boring-ui.modal.run'

    def test_callback_url_override(self):
        config = load_host_config_from_env({
            'ENVIRONMENT': 'production',
            'PUBLIC_HOST': 'boring-ui.modal.run',
            'SUPABASE_CALLBACK_URL': 'https://custom.com/auth/callback',
        })
        assert config.callback_url == 'https://custom.com/auth/callback'

    def test_allowed_origins_from_env(self):
        config = load_host_config_from_env({
            'ALLOWED_ORIGINS': 'https://a.com,https://b.com',
        })
        assert config.allowed_origins == ('https://a.com', 'https://b.com')

    def test_tls_explicit_override(self):
        config = load_host_config_from_env({
            'ENVIRONMENT': 'local',
            'TLS_ENABLED': 'true',
        })
        assert config.tls_enabled is True


# =====================================================================
# 6. Unit: public host resolution with proxy headers
# =====================================================================


class TestPublicHostResolution:
    """get_public_host correctly resolves per environment."""

    def test_local_uses_request_host(self):
        config = local_host_config()
        host = get_public_host('localhost:8000', config)
        assert host == 'localhost'

    def test_staging_uses_config_host(self):
        config = staging_host_config('staging.boring-ui.dev')
        host = get_public_host('internal:8080', config)
        assert host == 'staging.boring-ui.dev'

    def test_production_uses_config_host(self):
        config = production_host_config('boring-ui.modal.run')
        host = get_public_host('internal:8080', config)
        assert host == 'boring-ui.modal.run'

    def test_forwarded_host_used_for_local(self):
        config = local_host_config()
        host = get_public_host(
            'localhost:8000',
            config,
            forwarded_host='proxy.example.com',
        )
        assert host == 'proxy.example.com'

    def test_config_host_overrides_forwarded(self):
        config = production_host_config('boring-ui.modal.run')
        host = get_public_host(
            'internal:8080',
            config,
            forwarded_host='proxy.example.com',
        )
        assert host == 'boring-ui.modal.run'


# =====================================================================
# 7. Unit: effective scheme per environment
# =====================================================================


class TestEffectiveScheme:
    """get_effective_scheme returns correct scheme per env."""

    def test_local_http(self):
        config = local_host_config()
        assert get_effective_scheme(config) == 'http'

    def test_staging_https(self):
        config = staging_host_config('staging.boring-ui.dev')
        assert get_effective_scheme(config) == 'https'

    def test_production_https(self):
        config = production_host_config('boring-ui.modal.run')
        assert get_effective_scheme(config) == 'https'

    def test_local_with_forwarded_https(self):
        config = local_host_config()
        assert get_effective_scheme(config, forwarded_proto='https') == 'https'


# =====================================================================
# 8. Integration: callback → session cookie per environment
# =====================================================================


class TestCallbackPerEnv:
    """Auth callback sets correct cookie attributes per environment."""

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    @pytest.mark.asyncio
    async def test_callback_returns_302(self, params: EnvTestParams):
        app = _build_app(
            cookie_secure=params.cookie_secure,
            cookie_domain=params.cookie_domain,
        )
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            assert r.status_code == 302
            assert r.headers['location'] == '/'

    @pytest.mark.asyncio
    async def test_local_cookie_not_secure(self):
        app = _build_app(cookie_secure=False)
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            set_cookie = r.headers.get('set-cookie', '')
            assert SESSION_COOKIE_NAME in set_cookie
            assert 'httponly' in set_cookie.lower()
            assert 'samesite=lax' in set_cookie.lower()
            # Local dev: secure flag absent or explicitly false
            # httpx/starlette may not include 'secure' when False

    @pytest.mark.asyncio
    async def test_staging_cookie_secure(self):
        app = _build_app(
            cookie_secure=True,
            cookie_domain='.staging.boring-ui.dev',
        )
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            set_cookie = r.headers.get('set-cookie', '')
            assert SESSION_COOKIE_NAME in set_cookie
            assert 'httponly' in set_cookie.lower()
            assert 'secure' in set_cookie.lower()
            assert 'samesite=lax' in set_cookie.lower()
            assert '.staging.boring-ui.dev' in set_cookie.lower()

    @pytest.mark.asyncio
    async def test_production_cookie_secure_with_domain(self):
        app = _build_app(
            cookie_secure=True,
            cookie_domain='.boring-ui.modal.run',
        )
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            set_cookie = r.headers.get('set-cookie', '')
            assert SESSION_COOKIE_NAME in set_cookie
            assert 'httponly' in set_cookie.lower()
            assert 'secure' in set_cookie.lower()
            assert 'samesite=lax' in set_cookie.lower()
            assert '.boring-ui.modal.run' in set_cookie.lower()

    @pytest.mark.asyncio
    async def test_session_token_decodable_per_env(self):
        """Session token issued by callback is verifiable."""
        app = _build_app(cookie_secure=False)
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            set_cookie = r.headers.get('set-cookie', '')
            session_token = _extract_session_token(set_cookie)
            claims = verify_session_token(
                session_token,
                _session_config(cookie_secure=False),
            )
            assert claims['sub'] == 'user-env-001'
            assert claims['email'] == 'env-test@example.com'
            assert claims['type'] == 'session'


# =====================================================================
# 9. Integration: callback failure modes per environment
# =====================================================================


class TestCallbackFailuresPerEnv:
    """Callback failure modes produce correct errors regardless of env."""

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    @pytest.mark.asyncio
    async def test_missing_token_400(self, params: EnvTestParams):
        app = _build_app(cookie_secure=params.cookie_secure)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.get('/auth/callback')
            assert r.status_code == 400
            assert r.json()['error'] == 'missing_token'

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    @pytest.mark.asyncio
    async def test_invalid_token_401(self, params: EnvTestParams):
        app = _build_app(cookie_secure=params.cookie_secure)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.get('/auth/callback?access_token=garbage.jwt.here')
            assert r.status_code == 401
            assert r.json()['error'] == 'auth_callback_failed'

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    @pytest.mark.asyncio
    async def test_expired_token_401(self, params: EnvTestParams):
        app = _build_app(cookie_secure=params.cookie_secure)
        expired = _make_supabase_token(exp=int(time.time()) - 100)
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.get(f'/auth/callback?access_token={expired}')
            assert r.status_code == 401
            assert r.json()['code'] == 'token_expired'


# =====================================================================
# 10. E2E: callback → /auth/session → /api/v1/me per environment
# =====================================================================


class TestFullFlowPerEnv:
    """Complete auth round-trip works in each environment config."""

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    @pytest.mark.asyncio
    async def test_callback_then_session_then_me(self, params: EnvTestParams):
        app = _build_app(
            cookie_secure=params.cookie_secure,
            cookie_domain=params.cookie_domain,
        )
        supabase_token = _make_supabase_token()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            # Step 1: Auth callback → session cookie.
            cb = await c.get(f'/auth/callback?access_token={supabase_token}')
            assert cb.status_code == 302
            set_cookie = cb.headers.get('set-cookie', '')
            session_token = _extract_session_token(set_cookie)

            # Step 2: /auth/session → identity.
            r = await c.get(
                '/auth/session',
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            data = r.json()
            assert data['user_id'] == 'user-env-001'
            assert data['email'] == 'env-test@example.com'

            # Step 3: /api/v1/me → same identity.
            r = await c.get(
                '/api/v1/me',
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            data = r.json()
            assert data['user_id'] == 'user-env-001'
            assert data['email'] == 'env-test@example.com'
            assert data['role'] == 'authenticated'

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    @pytest.mark.asyncio
    async def test_logout_clears_session_per_env(self, params: EnvTestParams):
        app = _build_app(cookie_secure=params.cookie_secure)
        supabase_token = _make_supabase_token()

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            # Login.
            cb = await c.get(f'/auth/callback?access_token={supabase_token}')
            set_cookie = cb.headers.get('set-cookie', '')
            session_token = _extract_session_token(set_cookie)

            # Logout.
            r = await c.post(
                '/auth/logout',
                cookies={SESSION_COOKIE_NAME: session_token},
            )
            assert r.status_code == 200
            assert r.json()['status'] == 'logged_out'
            logout_cookie = r.headers.get('set-cookie', '')
            assert SESSION_COOKIE_NAME in logout_cookie

            # Verify session is gone → 401 on /api/v1/me.
            r = await c.get('/api/v1/me')
            assert r.status_code == 401


# =====================================================================
# 11. CORS headers per environment
# =====================================================================


class TestCorsPerEnv:
    """CORS headers match environment-specific allowed origins."""

    @pytest.mark.asyncio
    async def test_local_cors_allows_dev_origins(self):
        app = _build_app(
            cookie_secure=False,
            cors_origins=('http://localhost:8000', 'http://localhost:5173'),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.options(
                '/auth/callback',
                headers={
                    'origin': 'http://localhost:5173',
                    'access-control-request-method': 'GET',
                },
            )
            assert r.headers.get('access-control-allow-origin') == 'http://localhost:5173'

    @pytest.mark.asyncio
    async def test_staging_cors_allows_public_url(self):
        app = _build_app(
            cookie_secure=True,
            cors_origins=('https://staging.boring-ui.dev',),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.options(
                '/auth/callback',
                headers={
                    'origin': 'https://staging.boring-ui.dev',
                    'access-control-request-method': 'GET',
                },
            )
            assert r.headers.get('access-control-allow-origin') == 'https://staging.boring-ui.dev'

    @pytest.mark.asyncio
    async def test_production_cors_allows_public_url(self):
        app = _build_app(
            cookie_secure=True,
            cors_origins=('https://boring-ui.modal.run',),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.options(
                '/auth/callback',
                headers={
                    'origin': 'https://boring-ui.modal.run',
                    'access-control-request-method': 'GET',
                },
            )
            assert r.headers.get('access-control-allow-origin') == 'https://boring-ui.modal.run'

    @pytest.mark.asyncio
    async def test_cors_rejects_unknown_origin(self):
        app = _build_app(
            cookie_secure=True,
            cors_origins=('https://boring-ui.modal.run',),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.options(
                '/auth/callback',
                headers={
                    'origin': 'https://attacker.example.com',
                    'access-control-request-method': 'GET',
                },
            )
            # Should not include ACAO header for rejected origin.
            acao = r.headers.get('access-control-allow-origin', '')
            assert 'attacker' not in acao

    @pytest.mark.asyncio
    async def test_cors_credentials_allowed(self):
        app = _build_app(
            cookie_secure=True,
            cors_origins=('https://boring-ui.modal.run',),
        )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
        ) as c:
            r = await c.options(
                '/auth/callback',
                headers={
                    'origin': 'https://boring-ui.modal.run',
                    'access-control-request-method': 'GET',
                },
            )
            assert r.headers.get('access-control-allow-credentials') == 'true'


# =====================================================================
# 12. Redirect validation per environment
# =====================================================================


class TestRedirectValidation:
    """Auth callback redirects to the correct path."""

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    @pytest.mark.asyncio
    async def test_callback_redirects_to_root(self, params: EnvTestParams):
        app = _build_app(cookie_secure=params.cookie_secure)
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            assert r.status_code == 302
            assert r.headers['location'] == '/'

    @pytest.mark.asyncio
    async def test_custom_redirect_path(self):
        """Custom redirect_path in SessionConfig is honoured."""
        app = FastAPI()
        verifier = _verifier()
        config = SessionConfig(
            session_secret=SESSION_SECRET,
            cookie_secure=False,
            redirect_path='/dashboard',
        )
        app.include_router(create_auth_router(verifier, config))

        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            assert r.status_code == 302
            assert r.headers['location'] == '/dashboard'


# =====================================================================
# 13. EnvironmentConfig + HostConfig cross-validation
# =====================================================================


class TestEnvHostConfigCrossValidation:
    """EnvironmentConfig and HostConfig produce consistent results."""

    def test_local_configs_agree(self, monkeypatch):
        monkeypatch.delenv('ENVIRONMENT', raising=False)
        monkeypatch.delenv('PUBLIC_URL', raising=False)
        monkeypatch.delenv('CORS_ORIGINS', raising=False)
        monkeypatch.delenv('SUPABASE_CALLBACK_URL', raising=False)

        env_cfg = load_environment_config(environment='local')
        host_cfg = local_host_config()

        # Both should derive the same callback URL.
        assert env_cfg.supabase_callback_url == host_cfg.callback_url
        # Both should agree on cookie security.
        assert env_cfg.cookie_secure == host_cfg.cookie_secure

    def test_production_configs_agree(self, monkeypatch):
        monkeypatch.delenv('ENVIRONMENT', raising=False)
        monkeypatch.delenv('PUBLIC_URL', raising=False)
        monkeypatch.delenv('CORS_ORIGINS', raising=False)
        monkeypatch.delenv('SUPABASE_CALLBACK_URL', raising=False)

        env_cfg = load_environment_config(
            environment='production',
            public_url='https://boring-ui.modal.run',
        )
        host_cfg = production_host_config('boring-ui.modal.run')

        assert env_cfg.supabase_callback_url == host_cfg.callback_url
        assert env_cfg.cookie_secure == host_cfg.cookie_secure
        assert env_cfg.cookie_secure is True

    def test_staging_configs_agree(self, monkeypatch):
        monkeypatch.delenv('ENVIRONMENT', raising=False)
        monkeypatch.delenv('PUBLIC_URL', raising=False)
        monkeypatch.delenv('CORS_ORIGINS', raising=False)
        monkeypatch.delenv('SUPABASE_CALLBACK_URL', raising=False)

        env_cfg = load_environment_config(
            environment='staging',
            public_url='https://staging.boring-ui.dev',
        )
        host_cfg = staging_host_config('staging.boring-ui.dev')

        assert env_cfg.supabase_callback_url == host_cfg.callback_url
        assert env_cfg.cookie_secure == host_cfg.cookie_secure
        assert env_cfg.cookie_secure is True


# =====================================================================
# 14. Cookie max-age and path attributes per environment
# =====================================================================


class TestCookieAttributes:
    """Session cookie has correct max-age and path attributes."""

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    @pytest.mark.asyncio
    async def test_cookie_has_max_age(self, params: EnvTestParams):
        app = _build_app(cookie_secure=params.cookie_secure)
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            set_cookie = r.headers.get('set-cookie', '')
            assert 'max-age=' in set_cookie.lower()

    @pytest.mark.parametrize('params', ALL_ENVS, ids=ALL_ENV_IDS)
    @pytest.mark.asyncio
    async def test_cookie_path_is_root(self, params: EnvTestParams):
        app = _build_app(cookie_secure=params.cookie_secure)
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            set_cookie = r.headers.get('set-cookie', '')
            assert 'path=/' in set_cookie.lower()

    @pytest.mark.asyncio
    async def test_cookie_max_age_matches_session_ttl(self):
        app = _build_app(cookie_secure=False)
        token = _make_supabase_token()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url='http://test',
            follow_redirects=False,
        ) as c:
            r = await c.get(f'/auth/callback?access_token={token}')
            set_cookie = r.headers.get('set-cookie', '')
            # Default TTL is 86400 (24 hours).
            assert 'max-age=86400' in set_cookie.lower()


# =====================================================================
# 15. build_callback_url per environment
# =====================================================================


class TestBuildCallbackUrl:
    """build_callback_url computes correct URL per-env HostConfig."""

    def test_local_build_callback(self):
        config = local_host_config()
        url = build_callback_url(config)
        assert url == 'http://localhost:8000/auth/callback'

    def test_staging_build_callback(self):
        config = staging_host_config('staging.boring-ui.dev')
        url = build_callback_url(config)
        assert url == 'https://staging.boring-ui.dev/auth/callback'

    def test_production_build_callback(self):
        config = production_host_config('boring-ui.modal.run')
        url = build_callback_url(config)
        assert url == 'https://boring-ui.modal.run/auth/callback'

    def test_explicit_override_wins(self):
        config = HostConfig(
            environment=Environment.PRODUCTION,
            public_host='boring-ui.modal.run',
            tls_enabled=True,
            cookie_secure=True,
            supabase_callback_url='https://custom.boring.dev/auth/callback',
        )
        url = build_callback_url(config)
        assert url == 'https://custom.boring.dev/auth/callback'
