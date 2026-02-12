"""Unit tests for internal service-to-service authentication."""
import time

import pytest
from unittest.mock import MagicMock

from boring_ui.api.internal_auth import (
    InternalAuthConfig,
    InternalAuthMiddleware,
    generate_auth_token,
    validate_auth_token,
    DEFAULT_MAX_SKEW,
)


SECRET = 'test-secret-at-least-32-chars-long!'
NOW = 1700000000  # fixed timestamp for deterministic tests


class TestGenerateAuthToken:

    def test_format(self):
        token = generate_auth_token(SECRET, timestamp=NOW)
        parts = token.split(':')
        assert len(parts) == 3
        assert parts[0] == 'hmac-sha256'
        assert parts[1] == str(NOW)
        assert len(parts[2]) == 64  # sha256 hex

    def test_deterministic(self):
        t1 = generate_auth_token(SECRET, timestamp=NOW)
        t2 = generate_auth_token(SECRET, timestamp=NOW)
        assert t1 == t2

    def test_different_secrets_differ(self):
        t1 = generate_auth_token('secret-a-xxxxxxxxxxxxxxxxxxxxxxxx', timestamp=NOW)
        t2 = generate_auth_token('secret-b-xxxxxxxxxxxxxxxxxxxxxxxx', timestamp=NOW)
        assert t1 != t2

    def test_different_timestamps_differ(self):
        t1 = generate_auth_token(SECRET, timestamp=NOW)
        t2 = generate_auth_token(SECRET, timestamp=NOW + 1)
        assert t1 != t2

    def test_defaults_to_current_time(self):
        token = generate_auth_token(SECRET)
        ts = int(token.split(':')[1])
        assert abs(ts - int(time.time())) < 5


class TestValidateAuthToken:

    def test_valid_token(self):
        token = generate_auth_token(SECRET, timestamp=NOW)
        valid, reason = validate_auth_token(token, SECRET, now=NOW)
        assert valid is True
        assert reason == ''

    def test_within_skew(self):
        token = generate_auth_token(SECRET, timestamp=NOW)
        valid, reason = validate_auth_token(
            token, SECRET, now=NOW + DEFAULT_MAX_SKEW - 1,
        )
        assert valid is True

    def test_expired_token(self):
        token = generate_auth_token(SECRET, timestamp=NOW)
        valid, reason = validate_auth_token(
            token, SECRET, now=NOW + DEFAULT_MAX_SKEW + 1,
        )
        assert valid is False
        assert 'expired' in reason.lower()

    def test_future_token_within_skew(self):
        token = generate_auth_token(SECRET, timestamp=NOW + 100)
        valid, reason = validate_auth_token(token, SECRET, now=NOW)
        assert valid is True

    def test_future_token_beyond_skew(self):
        token = generate_auth_token(SECRET, timestamp=NOW + DEFAULT_MAX_SKEW + 100)
        valid, reason = validate_auth_token(token, SECRET, now=NOW)
        assert valid is False
        assert 'expired' in reason.lower()

    def test_wrong_secret(self):
        token = generate_auth_token(SECRET, timestamp=NOW)
        valid, reason = validate_auth_token(
            token, 'wrong-secret-xxxxxxxxxxxxxxxxxxxxxxxx', now=NOW,
        )
        assert valid is False
        assert 'signature' in reason.lower()

    def test_empty_token(self):
        valid, reason = validate_auth_token('', SECRET, now=NOW)
        assert valid is False
        assert 'missing' in reason.lower()

    def test_malformed_token(self):
        valid, reason = validate_auth_token('garbage', SECRET, now=NOW)
        assert valid is False
        assert 'malformed' in reason.lower()

    def test_wrong_scheme(self):
        valid, reason = validate_auth_token(
            f'bearer:{NOW}:abc123', SECRET, now=NOW,
        )
        assert valid is False
        assert 'scheme' in reason.lower()

    def test_non_numeric_timestamp(self):
        valid, reason = validate_auth_token(
            'hmac-sha256:notanumber:abc123', SECRET, now=NOW,
        )
        assert valid is False
        assert 'timestamp' in reason.lower()

    def test_tampered_signature(self):
        token = generate_auth_token(SECRET, timestamp=NOW)
        parts = token.split(':')
        parts[2] = 'a' * 64  # replace signature
        tampered = ':'.join(parts)
        valid, reason = validate_auth_token(tampered, SECRET, now=NOW)
        assert valid is False
        assert 'signature' in reason.lower()

    def test_tampered_timestamp(self):
        token = generate_auth_token(SECRET, timestamp=NOW)
        parts = token.split(':')
        parts[1] = str(NOW + 1)  # change timestamp without re-signing
        tampered = ':'.join(parts)
        valid, reason = validate_auth_token(tampered, SECRET, now=NOW)
        assert valid is False
        assert 'signature' in reason.lower()

    def test_custom_max_skew(self):
        token = generate_auth_token(SECRET, timestamp=NOW)
        # 10s skew, 11s difference -> expired
        valid, reason = validate_auth_token(
            token, SECRET, max_skew_seconds=10, now=NOW + 11,
        )
        assert valid is False
        # 10s skew, 9s difference -> valid
        valid, reason = validate_auth_token(
            token, SECRET, max_skew_seconds=10, now=NOW + 9,
        )
        assert valid is True


class TestInternalAuthMiddleware:
    """Test middleware integration via FastAPI test client."""

    @pytest.fixture
    def app(self):
        from fastapi import FastAPI
        app = FastAPI()

        @app.get('/api/test')
        async def protected():
            return {'ok': True}

        @app.get('/healthz')
        async def healthz():
            return {'status': 'ok'}

        @app.get('/__meta/version')
        async def version():
            return {'version': '0.1.0'}

        auth_config = InternalAuthConfig(secret=SECRET)
        app.add_middleware(InternalAuthMiddleware, auth_config=auth_config)
        return app

    @pytest.mark.asyncio
    async def test_protected_route_requires_auth(self, app):
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            resp = await c.get('/api/test')
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_protected_route_with_valid_token(self, app):
        from httpx import AsyncClient, ASGITransport
        token = generate_auth_token(SECRET)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            resp = await c.get(
                '/api/test',
                headers={'X-Workspace-Internal-Auth': token},
            )
        assert resp.status_code == 200
        assert resp.json() == {'ok': True}

    @pytest.mark.asyncio
    async def test_protected_route_with_invalid_token(self, app):
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            resp = await c.get(
                '/api/test',
                headers={'X-Workspace-Internal-Auth': 'bad-token'},
            )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_healthz_exempt(self, app):
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            resp = await c.get('/healthz')
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_meta_exempt(self, app):
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            resp = await c.get('/__meta/version')
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_disabled_auth_passes_all(self):
        from fastapi import FastAPI
        from httpx import AsyncClient, ASGITransport

        app = FastAPI()

        @app.get('/api/test')
        async def protected():
            return {'ok': True}

        auth_config = InternalAuthConfig(secret=SECRET, enabled=False)
        app.add_middleware(InternalAuthMiddleware, auth_config=auth_config)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test',
        ) as c:
            resp = await c.get('/api/test')
        assert resp.status_code == 200


class TestInternalAuthConfig:

    def test_defaults(self):
        cfg = InternalAuthConfig(secret='s' * 32)
        assert cfg.max_skew_seconds == DEFAULT_MAX_SKEW
        assert cfg.enabled is True

    def test_custom_skew(self):
        cfg = InternalAuthConfig(secret='s' * 32, max_skew_seconds=60)
        assert cfg.max_skew_seconds == 60

    def test_disabled(self):
        cfg = InternalAuthConfig(secret='s' * 32, enabled=False)
        assert cfg.enabled is False
