"""Tests for workspace transport implementations (bd-1adh.4.1)."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from boring_ui.api.transport import (
    HTTPInternalTransport,
    SpritesProxyTransport,
    WorkspaceResponse,
    HealthStatus,
)


class TestHTTPInternalTransport:
    """Tests for HTTP internal transport."""

    @pytest.mark.asyncio
    async def test_successful_request(self):
        """HTTP transport sends successful request."""
        transport = HTTPInternalTransport("http://localhost:9000")

        # Mock aiohttp
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.read = AsyncMock(return_value=b'{"status":"ok"}')

            mock_session.request.return_value.__aenter__.return_value = (
                mock_response
            )

            response = await transport.request(
                "GET",
                "/internal/v1/files/tree",
                headers={"custom": "header"},
            )

            assert response.status_code == 200
            assert response.body == b'{"status":"ok"}'
            assert response.transport_type == "http"
            assert "custom" not in response.headers  # Custom header in req, not resp

    @pytest.mark.asyncio
    async def test_request_with_trace_id(self):
        """HTTP transport includes trace ID in headers."""
        transport = HTTPInternalTransport("http://localhost:9000")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {}
            mock_response.read = AsyncMock(return_value=b"")

            mock_session.request.return_value.__aenter__.return_value = (
                mock_response
            )

            await transport.request(
                "GET",
                "/internal/v1/files/tree",
                trace_id="trace-123",
            )

            # Verify trace ID was in request headers
            call_kwargs = mock_session.request.call_args[1]
            assert call_kwargs["headers"]["X-Trace-ID"] == "trace-123"

    @pytest.mark.asyncio
    async def test_request_timeout(self):
        """HTTP transport raises on timeout."""
        transport = HTTPInternalTransport("http://localhost:9000")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            mock_session.request.return_value.__aenter__.side_effect = (
                asyncio.TimeoutError()
            )

            with pytest.raises(asyncio.TimeoutError):
                await transport.request(
                    "GET",
                    "/internal/v1/files/tree",
                    timeout_sec=1.0,
                )

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Health check returns HEALTHY on 200."""
        transport = HTTPInternalTransport("http://localhost:9000")

        with patch.object(transport, "request") as mock_request:
            mock_request.return_value = WorkspaceResponse(
                status_code=200,
                headers={},
                body=b"",
                elapsed_sec=0.1,
                transport_type="http",
            )

            status = await transport.health_check()
            assert status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        """Health check returns DEGRADED on non-200 status."""
        transport = HTTPInternalTransport("http://localhost:9000")

        with patch.object(transport, "request") as mock_request:
            mock_request.return_value = WorkspaceResponse(
                status_code=503,
                headers={},
                body=b"",
                elapsed_sec=0.1,
                transport_type="http",
            )

            status = await transport.health_check()
            assert status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Health check returns UNAVAILABLE on timeout."""
        transport = HTTPInternalTransport("http://localhost:9000")

        with patch.object(
            transport, "request", side_effect=asyncio.TimeoutError()
        ):
            status = await transport.health_check()
            assert status == HealthStatus.UNAVAILABLE


class TestSpritesProxyTransport:
    """Tests for Sprites proxy transport."""

    def test_initialization(self):
        """Sprites transport initializes with required parameters."""
        transport = SpritesProxyTransport(
            sprites_token="test-token",
            sprite_name="prod-sprite",
            local_api_port=8001,
        )

        assert transport.sprites_token == "test-token"
        assert transport.sprite_name == "prod-sprite"
        assert transport.local_api_port == 8001

    def test_build_http_request_simple(self):
        """Build simple GET request without body."""
        transport = SpritesProxyTransport(
            sprites_token="token",
            sprite_name="sprite",
            local_api_port=8001,
        )

        request_bytes = transport._build_http_request(
            "GET",
            "/internal/v1/files/tree",
            {"Connection": "close"},
            None,
        )

        request_str = request_bytes.decode()
        assert "GET /internal/v1/files/tree HTTP/1.1" in request_str
        assert "Connection: close" in request_str
        assert request_str.endswith("\r\n")

    def test_build_http_request_with_body(self):
        """Build POST request with body and Content-Length."""
        transport = SpritesProxyTransport(
            sprites_token="token",
            sprite_name="sprite",
            local_api_port=8001,
        )

        body = b'{"content":"test"}'
        request_bytes = transport._build_http_request(
            "POST",
            "/internal/v1/files/file",
            {"Connection": "close"},
            body,
        )

        request_str = request_bytes.decode("utf-8", errors="replace")
        assert "POST /internal/v1/files/file HTTP/1.1" in request_str
        assert f"Content-Length: {len(body)}" in request_str
        assert request_bytes.endswith(body)

    def test_parse_http_response_success(self):
        """Parse successful HTTP response."""
        transport = SpritesProxyTransport(
            sprites_token="token",
            sprite_name="sprite",
            local_api_port=8001,
        )

        raw = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 13\r\n"
            b"\r\n"
            b'{"status":"ok"}'
        )

        status, headers, body = transport._parse_http_response(raw)

        assert status == 200
        assert headers["Content-Type"] == "application/json"
        assert body == b'{"status":"ok"}'

    def test_parse_http_response_empty_body(self):
        """Parse HTTP response with empty body."""
        transport = SpritesProxyTransport(
            sprites_token="token",
            sprite_name="sprite",
            local_api_port=8001,
        )

        raw = b"HTTP/1.1 404 Not Found\r\n\r\n"

        status, headers, body = transport._parse_http_response(raw)

        assert status == 404
        assert body == b""

    def test_parse_http_response_malformed_status(self):
        """Parse malformed HTTP response raises ValueError."""
        transport = SpritesProxyTransport(
            sprites_token="token",
            sprite_name="sprite",
            local_api_port=8001,
        )

        raw = b"INVALID HTTP LINE\r\n\r\n"

        with pytest.raises(ValueError, match="Malformed"):
            transport._parse_http_response(raw)

    def test_parse_http_response_invalid_status_code(self):
        """Parse response with invalid status code raises ValueError."""
        transport = SpritesProxyTransport(
            sprites_token="token",
            sprite_name="sprite",
            local_api_port=8001,
        )

        raw = b"HTTP/1.1 INVALID \r\n\r\n"

        with pytest.raises(ValueError, match="Invalid status code"):
            transport._parse_http_response(raw)

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Sprites health check returns HEALTHY on 200."""
        transport = SpritesProxyTransport(
            sprites_token="token",
            sprite_name="sprite",
            local_api_port=8001,
        )

        with patch.object(transport, "request") as mock_request:
            mock_request.return_value = WorkspaceResponse(
                status_code=200,
                headers={},
                body=b"",
                elapsed_sec=0.1,
                transport_type="sprites_proxy",
            )

            status = await transport.health_check()
            assert status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Sprites health check returns UNAVAILABLE on timeout."""
        transport = SpritesProxyTransport(
            sprites_token="token",
            sprite_name="sprite",
            local_api_port=8001,
        )

        with patch.object(
            transport, "request", side_effect=asyncio.TimeoutError()
        ):
            status = await transport.health_check()
            assert status == HealthStatus.UNAVAILABLE


class TestWorkspaceResponse:
    """Tests for WorkspaceResponse dataclass."""

    def test_response_creation(self):
        """Create WorkspaceResponse with valid data."""
        response = WorkspaceResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body=b'{"test":"data"}',
            elapsed_sec=0.5,
            transport_type="http",
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.body == b'{"test":"data"}'
        assert response.elapsed_sec == 0.5
        assert response.transport_type == "http"
        assert response.error_code is None

    def test_response_with_error_code(self):
        """Create WorkspaceResponse with error code."""
        response = WorkspaceResponse(
            status_code=502,
            headers={},
            body=b"",
            elapsed_sec=0.1,
            transport_type="sprites_proxy",
            error_code="sprites_handshake_timeout",
        )

        assert response.status_code == 502
        assert response.error_code == "sprites_handshake_timeout"
