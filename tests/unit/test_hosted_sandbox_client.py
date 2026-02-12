"""Tests for HostedSandboxClient (bd-1pwb.5.1).

Verifies:
- Per-operation routing helpers call correct endpoints
- Capability token injection via Authorization header
- Service token signing via X-Service-Token header
- Trace ID and request ID propagation
- Observability stats
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from boring_ui.api.modules.sandbox.hosted_client import (
    HostedSandboxClient,
    SandboxClientConfig,
)


@pytest.fixture
def mock_signer():
    signer = MagicMock()
    signer.sign_request.return_value = "service-jwt-token"
    return signer


@pytest.fixture
def config(mock_signer):
    return SandboxClientConfig(
        internal_url="http://127.0.0.1:2469",
        capability_token="default-cap-token",
        timeout_seconds=10,
        max_retries=2,
        service_signer=mock_signer,
    )


@pytest.fixture
def client(config):
    return HostedSandboxClient(config)


def _mock_response(json_data=None, status_code=200):
    """Create a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.request = MagicMock()
    return response


class TestOperationHelpers:
    """Per-operation helpers route to correct internal endpoints."""

    @pytest.mark.asyncio
    async def test_list_files(self, client):
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({"files": ["a.py"]})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.list_files("src/")

            call_args = mock_instance.request.call_args
            assert call_args[0][0] == "GET"
            assert "/internal/v1/files/list" in call_args[0][1]
            assert call_args[1]["params"]["path"] == "src/"
            assert result == {"files": ["a.py"]}

    @pytest.mark.asyncio
    async def test_read_file(self, client):
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({"content": "hello"})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.read_file("main.py")

            call_args = mock_instance.request.call_args
            assert call_args[0][0] == "GET"
            assert "/internal/v1/files/read" in call_args[0][1]
            assert call_args[1]["params"]["path"] == "main.py"
            assert result == {"content": "hello"}

    @pytest.mark.asyncio
    async def test_write_file(self, client):
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({"success": True})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.write_file("out.txt", "data")

            call_args = mock_instance.request.call_args
            assert call_args[0][0] == "POST"
            assert "/internal/v1/files/write" in call_args[0][1]
            assert call_args[1]["params"]["path"] == "out.txt"
            assert call_args[1]["params"]["content"] == "data"

    @pytest.mark.asyncio
    async def test_git_status(self, client):
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({"branch": "main"})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.git_status()

            call_args = mock_instance.request.call_args
            assert call_args[0][0] == "GET"
            assert "/internal/v1/git/status" in call_args[0][1]
            assert result == {"branch": "main"}

    @pytest.mark.asyncio
    async def test_git_diff(self, client):
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({"diff": "+line"})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.git_diff("staged")

            call_args = mock_instance.request.call_args
            assert call_args[0][0] == "GET"
            assert "/internal/v1/git/diff" in call_args[0][1]
            assert call_args[1]["params"]["context"] == "staged"

    @pytest.mark.asyncio
    async def test_exec_run(self, client):
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({"exit_code": 0})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await client.exec_run("ls -la", timeout_seconds=60)

            call_args = mock_instance.request.call_args
            assert call_args[0][0] == "POST"
            assert "/internal/v1/exec/run" in call_args[0][1]
            assert call_args[1]["params"]["command"] == "ls -la"
            assert call_args[1]["params"]["timeout_seconds"] == 60


class TestCapabilityTokenInjection:
    """Capability token injection via Authorization header."""

    @pytest.mark.asyncio
    async def test_default_capability_token(self, client):
        """Default capability_token from config is used when none provided."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.list_files()

            headers = mock_instance.request.call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer default-cap-token"

    @pytest.mark.asyncio
    async def test_per_request_capability_token_overrides(self, client):
        """Per-request capability_token overrides config default."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.list_files(capability_token="per-request-token")

            headers = mock_instance.request.call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer per-request-token"

    @pytest.mark.asyncio
    async def test_no_auth_header_when_no_token(self):
        """No Authorization header when no token configured."""
        config = SandboxClientConfig(internal_url="http://127.0.0.1:2469")
        client = HostedSandboxClient(config)

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.list_files()

            headers = mock_instance.request.call_args[1]["headers"]
            assert "Authorization" not in headers


class TestServiceTokenSigning:
    """Service token signing via X-Service-Token header."""

    @pytest.mark.asyncio
    async def test_service_token_added(self, client, mock_signer):
        """X-Service-Token header is added when signer configured."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.list_files()

            headers = mock_instance.request.call_args[1]["headers"]
            assert headers["X-Service-Token"] == "service-jwt-token"
            mock_signer.sign_request.assert_called_once_with(ttl_seconds=60)

    @pytest.mark.asyncio
    async def test_no_service_token_without_signer(self):
        """No X-Service-Token when signer not configured."""
        config = SandboxClientConfig(internal_url="http://127.0.0.1:2469")
        client = HostedSandboxClient(config)

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.list_files()

            headers = mock_instance.request.call_args[1]["headers"]
            assert "X-Service-Token" not in headers


class TestTraceContext:
    """Trace ID and request ID propagation."""

    @pytest.mark.asyncio
    async def test_trace_id_generated(self, client):
        """X-Trace-ID header is auto-generated."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.list_files()

            headers = mock_instance.request.call_args[1]["headers"]
            assert "X-Trace-ID" in headers
            assert len(headers["X-Trace-ID"]) > 0

    @pytest.mark.asyncio
    async def test_request_id_increments(self, client):
        """X-Request-ID increments with each request."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.list_files()
            id1 = mock_instance.request.call_args[1]["headers"]["X-Request-ID"]

            await client.read_file("x.py")
            id2 = mock_instance.request.call_args[1]["headers"]["X-Request-ID"]

            assert id1 != id2


class TestObservability:
    """Client observability stats."""

    @pytest.mark.asyncio
    async def test_request_count_tracked(self, client):
        """Request count increments."""
        assert client.get_stats()["total_requests"] == 0

        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response({})
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            await client.list_files()
            await client.read_file("a.py")

        assert client.get_stats()["total_requests"] == 2

    def test_stats_include_config(self, client):
        """Stats include configuration details."""
        stats = client.get_stats()
        assert stats["internal_url"] == "http://127.0.0.1:2469"
        assert stats["timeout_seconds"] == 10


class TestErrorHandling:
    """Error handling for HTTP errors."""

    @pytest.mark.asyncio
    async def test_http_error_raises(self, client):
        """HTTP errors are raised as httpx.HTTPStatusError."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response(
                {"detail": "Not Found"}, status_code=404
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(httpx.HTTPStatusError):
                await client.read_file("missing.py")

    @pytest.mark.asyncio
    async def test_500_error_raises(self, client):
        """Server errors are raised."""
        with patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.request.return_value = _mock_response(
                {"detail": "Internal Server Error"}, status_code=500
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            with pytest.raises(httpx.HTTPStatusError):
                await client.exec_run("bad-cmd")


class TestSandboxClientConfig:
    """SandboxClientConfig defaults and validation."""

    def test_defaults(self):
        config = SandboxClientConfig(internal_url="http://localhost:2469")
        assert config.capability_token == ""
        assert config.timeout_seconds == 30
        assert config.max_retries == 3
        assert config.enable_observability is True
        assert config.service_signer is None

    def test_custom_values(self, mock_signer):
        config = SandboxClientConfig(
            internal_url="http://10.0.0.1:9000",
            capability_token="tok-123",
            timeout_seconds=60,
            max_retries=5,
            enable_observability=False,
            service_signer=mock_signer,
        )
        assert config.internal_url == "http://10.0.0.1:9000"
        assert config.capability_token == "tok-123"
        assert config.timeout_seconds == 60
