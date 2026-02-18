"""Unit tests for startup health and compatibility checks."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from boring_ui.api.startup_checks import (
    CheckResult,
    StartupCheckError,
    build_workspace_service_url,
    build_startup_headers,
    check_healthz,
    check_version,
    run_startup_checks,
)
from boring_ui.api.config import SandboxConfig, SandboxServiceTarget


@pytest.fixture
def sandbox_config():
    """Valid sandbox config for testing."""
    return SandboxConfig(
        base_url='https://sprites.example.internal',
        sprite_name='workspace-a',
        api_token='token-value',
        session_token_secret='x' * 32,
        service_target=SandboxServiceTarget(
            host='workspace-service',
            port=8443,
            path='/api/workspace',
        ),
    )


class TestBuildUrl:
    def test_builds_url_with_path(self, sandbox_config):
        url = build_workspace_service_url(sandbox_config)
        assert url == 'http://workspace-service:8443/api/workspace'

    def test_strips_trailing_slash(self):
        config = SandboxConfig(
            base_url='https://sprites.example.internal',
            sprite_name='ws-a',
            api_token='tok',
            session_token_secret='x' * 32,
            service_target=SandboxServiceTarget(host='host', port=80, path='/'),
        )
        url = build_workspace_service_url(config)
        assert url == 'http://host:80'

    def test_build_startup_headers(self, sandbox_config):
        headers = build_startup_headers(sandbox_config)
        assert 'X-Workspace-Internal-Auth' in headers
        assert 'X-Workspace-API-Version' in headers


class TestCheckHealthz:

    @pytest.mark.asyncio
    async def test_healthy_ok(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': 'ok'}

        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await check_healthz('http://host:8080')

        assert result.passed is True
        assert result.name == 'healthz'

    @pytest.mark.asyncio
    async def test_passes_headers(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': 'ok'}

        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            headers = {'X-Workspace-API-Version': '0.1.0'}
            await check_healthz('http://host:8080', headers=headers)

            mock_client.get.assert_awaited_once_with(
                'http://host:8080/healthz',
                headers=headers,
            )

    @pytest.mark.asyncio
    async def test_healthy_degraded(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'status': 'degraded'}

        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await check_healthz('http://host:8080')

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_non_200_fails(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await check_healthz('http://host:8080')

        assert result.passed is False
        assert '503' in result.detail

    @pytest.mark.asyncio
    async def test_connection_refused(self):
        import httpx
        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_httpx.ConnectError = httpx.ConnectError
            mock_httpx.TimeoutException = httpx.TimeoutException
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError('refused')
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await check_healthz('http://host:8080')

        assert result.passed is False
        assert 'Connection refused' in result.detail

    @pytest.mark.asyncio
    async def test_timeout(self):
        import httpx
        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_httpx.ConnectError = httpx.ConnectError
            mock_httpx.TimeoutException = httpx.TimeoutException
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException('timeout')
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await check_healthz('http://host:8080')

        assert result.passed is False
        assert 'Timeout' in result.detail


class TestCheckVersion:

    @pytest.mark.asyncio
    async def test_compatible_version(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'version': '0.1.0'}

        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await check_version('http://host:8080')

        assert result.passed is True

    @pytest.mark.asyncio
    async def test_passes_headers(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'version': '0.1.0'}

        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            headers = {'X-Workspace-API-Version': '0.1.0'}
            await check_version('http://host:8080', headers=headers)

            mock_client.get.assert_awaited_once_with(
                'http://host:8080/__meta/version',
                headers=headers,
            )

    @pytest.mark.asyncio
    async def test_incompatible_version(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'version': '1.0.0'}

        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await check_version('http://host:8080')

        assert result.passed is False
        assert 'Incompatible' in result.detail

    @pytest.mark.asyncio
    async def test_missing_version_field(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}

        with patch('boring_ui.api.startup_checks.httpx') as mock_httpx:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await check_version('http://host:8080')

        assert result.passed is False


class TestRunStartupChecks:

    @pytest.mark.asyncio
    async def test_all_pass(self, sandbox_config):
        with patch('boring_ui.api.startup_checks.check_healthz') as mock_health, \
             patch('boring_ui.api.startup_checks.check_version') as mock_version:
            mock_health.return_value = CheckResult('healthz', True, 'ok')
            mock_version.return_value = CheckResult('version', True, '0.1.0')

            results = await run_startup_checks(sandbox_config)

        assert len(results) == 2
        assert all(r.passed for r in results)
        health_kwargs = mock_health.await_args.kwargs
        version_kwargs = mock_version.await_args.kwargs
        assert 'headers' in health_kwargs
        assert 'X-Workspace-Internal-Auth' in health_kwargs['headers']
        assert 'headers' in version_kwargs
        assert 'X-Workspace-API-Version' in version_kwargs['headers']

    @pytest.mark.asyncio
    async def test_fail_fast_raises(self, sandbox_config):
        with patch('boring_ui.api.startup_checks.check_healthz') as mock_health, \
             patch('boring_ui.api.startup_checks.check_version') as mock_version:
            mock_health.return_value = CheckResult('healthz', False, 'Connection refused')
            mock_version.return_value = CheckResult('version', True, '0.1.0')

            with pytest.raises(StartupCheckError) as exc:
                await run_startup_checks(sandbox_config, fail_fast=True)

            assert 'Connection refused' in str(exc.value)

    @pytest.mark.asyncio
    async def test_no_fail_fast_returns_failures(self, sandbox_config):
        with patch('boring_ui.api.startup_checks.check_healthz') as mock_health, \
             patch('boring_ui.api.startup_checks.check_version') as mock_version:
            mock_health.return_value = CheckResult('healthz', False, 'refused')
            mock_version.return_value = CheckResult('version', False, 'mismatch')

            results = await run_startup_checks(sandbox_config, fail_fast=False)

        assert len(results) == 2
        assert not any(r.passed for r in results)


class TestStartupCheckError:

    def test_formats_failures(self):
        err = StartupCheckError(['Connection refused', 'Version mismatch'])
        assert 'Connection refused' in str(err)
        assert 'Version mismatch' in str(err)
        assert len(err.failures) == 2
