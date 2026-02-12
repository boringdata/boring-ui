"""Unit tests for SpritesServicesClient."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from boring_ui.api.services_client import (
    CachedResult,
    CircuitBreaker,
    CircuitState,
    DEFAULT_CACHE_TTL,
    ServiceUnavailableError,
    SpritesServicesClient,
)
from boring_ui.api.config import SandboxConfig, SandboxServiceTarget, SpriteLayout


# ── Helpers ──


def _sandbox_config(**overrides) -> SandboxConfig:
    defaults = dict(
        base_url='https://sprites.internal',
        sprite_name='test-sprite',
        api_token='a' * 64,
        session_token_secret='b' * 64,
        service_target=SandboxServiceTarget(
            host='localhost', port=9000, path='/workspace',
        ),
        sprite_layout=SpriteLayout(),
    )
    defaults.update(overrides)
    return SandboxConfig(**defaults)


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


# ── CircuitBreaker tests ──


class TestCircuitBreaker:

    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert not cb.is_open

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_open

    def test_success_resets_count(self):
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10.0)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # Simulate recovery timeout elapsed
        cb._last_failure_time = time.monotonic() - 11.0
        assert cb.state == CircuitState.HALF_OPEN

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


# ── CachedResult tests ──


class TestCachedResult:

    def test_not_expired(self):
        c = CachedResult(value={'ok': True}, fetched_at=time.monotonic(), ttl=60.0)
        assert not c.is_expired

    def test_expired(self):
        c = CachedResult(
            value={'ok': True},
            fetched_at=time.monotonic() - 100.0,
            ttl=60.0,
        )
        assert c.is_expired

    def test_zero_ttl_expires_immediately(self):
        c = CachedResult(
            value={},
            fetched_at=time.monotonic() - 0.001,
            ttl=0.0,
        )
        assert c.is_expired


# ── SpritesServicesClient.check_health tests ──


class TestCheckHealth:

    @pytest.fixture
    def client(self):
        return SpritesServicesClient(
            _sandbox_config(),
            max_retries=0,
            cache_ttl=0.0,
        )

    @pytest.mark.asyncio
    async def test_healthy_ok(self, client):
        resp = _mock_response(200, {'status': 'ok'})
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_health()
        assert result['status'] == 'ok'

    @pytest.mark.asyncio
    async def test_healthy_degraded(self, client):
        resp = _mock_response(200, {'status': 'degraded'})
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_health()
        assert result['status'] == 'degraded'

    @pytest.mark.asyncio
    async def test_non_200_returns_unhealthy(self, client):
        resp = _mock_response(500)
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_health()
        assert result['status'] == 'unhealthy'

    @pytest.mark.asyncio
    async def test_unknown_status_returns_unhealthy(self, client):
        resp = _mock_response(200, {'status': 'broken'})
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_health()
        assert result['status'] == 'unhealthy'

    @pytest.mark.asyncio
    async def test_connection_error_returns_unhealthy(self, client):
        import httpx as httpx_mod
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(side_effect=httpx_mod.ConnectError('refused'))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_health()
        assert result['status'] == 'unhealthy'
        assert 'detail' in result

    @pytest.mark.asyncio
    async def test_cache_hit(self, client):
        """Second call within TTL returns cached value."""
        client._cache_ttl = 60.0
        resp = _mock_response(200, {'status': 'ok'})
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result1 = await client.check_health()
            # Second call should use cache
            result2 = await client.check_health()
            assert mock_ctx.request.call_count == 1
        assert result1 == result2


# ── SpritesServicesClient.check_version tests ──


class TestCheckVersion:

    @pytest.fixture
    def client(self):
        return SpritesServicesClient(
            _sandbox_config(),
            max_retries=0,
            cache_ttl=0.0,
        )

    @pytest.mark.asyncio
    async def test_compatible_version(self, client):
        resp = _mock_response(200, {'version': '0.1.0'})
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_version()
        assert result['version'] == '0.1.0'
        assert result['compatible'] is True

    @pytest.mark.asyncio
    async def test_incompatible_version(self, client):
        resp = _mock_response(200, {'version': '1.0.0'})
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_version()
        assert result['compatible'] is False
        assert 'detail' in result

    @pytest.mark.asyncio
    async def test_missing_version_field(self, client):
        resp = _mock_response(200, {'api': 'some'})
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_version()
        assert result['compatible'] is False
        assert result['version'] == ''

    @pytest.mark.asyncio
    async def test_non_200(self, client):
        resp = _mock_response(404)
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_version()
        assert result['compatible'] is False

    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        import httpx as httpx_mod
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(side_effect=httpx_mod.ConnectError('refused'))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_version()
        assert result['compatible'] is False

    @pytest.mark.asyncio
    async def test_cache_hit(self, client):
        client._cache_ttl = 60.0
        resp = _mock_response(200, {'version': '0.1.0'})
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            r1 = await client.check_version()
            r2 = await client.check_version()
            assert mock_ctx.request.call_count == 1
        assert r1 == r2


# ── SpritesServicesClient.is_ready tests ──


class TestIsReady:

    @pytest.fixture
    def client(self):
        return SpritesServicesClient(
            _sandbox_config(),
            max_retries=0,
            cache_ttl=0.0,
        )

    @pytest.mark.asyncio
    async def test_ready_when_healthy_and_compatible(self, client):
        health_resp = _mock_response(200, {'status': 'ok'})
        version_resp = _mock_response(200, {'version': '0.1.0'})
        call_count = 0

        async def side_effect(method, url, headers=None):
            nonlocal call_count
            call_count += 1
            if '/healthz' in url:
                return health_resp
            return version_resp

        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(side_effect=side_effect)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            assert await client.is_ready() is True

    @pytest.mark.asyncio
    async def test_not_ready_when_unhealthy(self, client):
        resp = _mock_response(500)
        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(return_value=resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            assert await client.is_ready() is False

    @pytest.mark.asyncio
    async def test_not_ready_when_incompatible(self, client):
        health_resp = _mock_response(200, {'status': 'ok'})
        version_resp = _mock_response(200, {'version': '1.0.0'})

        async def side_effect(method, url, headers=None):
            if '/healthz' in url:
                return health_resp
            return version_resp

        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(side_effect=side_effect)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            assert await client.is_ready() is False

    @pytest.mark.asyncio
    async def test_ready_when_degraded(self, client):
        health_resp = _mock_response(200, {'status': 'degraded'})
        version_resp = _mock_response(200, {'version': '0.1.0'})

        async def side_effect(method, url, headers=None):
            if '/healthz' in url:
                return health_resp
            return version_resp

        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(side_effect=side_effect)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            assert await client.is_ready() is True


# ── Retry behavior tests ──


class TestRetryBehavior:

    @pytest.mark.asyncio
    async def test_retries_on_connect_error(self):
        import httpx as httpx_mod
        client = SpritesServicesClient(
            _sandbox_config(),
            max_retries=2,
            retry_base_delay=0.001,
            retry_max_delay=0.01,
            cache_ttl=0.0,
        )
        success = _mock_response(200, {'status': 'ok'})
        call_count = 0

        async def side_effect(method, url, headers=None):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx_mod.ConnectError('refused')
            return success

        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(side_effect=side_effect)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_health()
        assert result['status'] == 'ok'
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        import httpx as httpx_mod
        client = SpritesServicesClient(
            _sandbox_config(),
            max_retries=1,
            retry_base_delay=0.001,
            retry_max_delay=0.01,
            cache_ttl=0.0,
        )
        success = _mock_response(200, {'status': 'ok'})
        call_count = 0

        async def side_effect(method, url, headers=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx_mod.ReadTimeout('timeout')
            return success

        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(side_effect=side_effect)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client.check_health()
        assert result['status'] == 'ok'
        assert call_count == 2


# ── Circuit breaker integration tests ──


class TestCircuitBreakerIntegration:

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        import httpx as httpx_mod
        client = SpritesServicesClient(
            _sandbox_config(),
            max_retries=0,
            cb_failure_threshold=2,
            cb_recovery_timeout=100.0,
            cache_ttl=0.0,
        )

        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(
                side_effect=httpx_mod.ConnectError('refused')
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # First two calls go through (and fail), opening the circuit
            await client.check_health()
            await client.check_health()
            assert client.circuit_state == CircuitState.OPEN

            # Third call should fail fast without making a request
            result = await client.check_health()
            assert result['status'] == 'unhealthy'
            # Only 2 actual requests made (the third was circuit-breaker rejected)
            assert mock_ctx.request.call_count == 2

    @pytest.mark.asyncio
    async def test_reset_circuit(self):
        import httpx as httpx_mod
        client = SpritesServicesClient(
            _sandbox_config(),
            max_retries=0,
            cb_failure_threshold=1,
            cache_ttl=0.0,
        )

        with patch('boring_ui.api.services_client.httpx.AsyncClient') as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.request = AsyncMock(
                side_effect=httpx_mod.ConnectError('refused')
            )
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await client.check_health()
            assert client.circuit_state == CircuitState.OPEN

        client.reset_circuit()
        assert client.circuit_state == CircuitState.CLOSED


# ── Cache management tests ──


class TestCacheManagement:

    def test_invalidate_cache(self):
        client = SpritesServicesClient(_sandbox_config())
        client._health_cache = CachedResult(
            value={'status': 'ok'}, fetched_at=time.monotonic(), ttl=60.0,
        )
        client._version_cache = CachedResult(
            value={'version': '0.1.0'}, fetched_at=time.monotonic(), ttl=60.0,
        )
        client.invalidate_cache()
        assert client._health_cache is None
        assert client._version_cache is None


# ── Client properties tests ──


class TestClientProperties:

    def test_base_url(self):
        client = SpritesServicesClient(_sandbox_config())
        assert client.base_url == 'http://localhost:9000/workspace'

    def test_circuit_state_default(self):
        client = SpritesServicesClient(_sandbox_config())
        assert client.circuit_state == CircuitState.CLOSED

    def test_auth_headers(self):
        client = SpritesServicesClient(_sandbox_config())
        headers = client._auth_headers()
        assert 'X-Workspace-Internal-Auth' in headers
        assert 'X-Workspace-API-Version' in headers
        assert headers['X-Workspace-Internal-Auth'].startswith('hmac-sha256:')
