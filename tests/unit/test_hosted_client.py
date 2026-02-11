"""Tests for hosted client retry/backoff behavior (bd-1adh.4.3)."""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from boring_ui.api.hosted_client import HostedClient, RetryPolicy
from boring_ui.api.transport import WorkspaceResponse, HealthStatus
from boring_ui.api.error_codes import TransportError


class TestRetryPolicy:
    """Tests for RetryPolicy configuration."""

    def test_default_retry_policy(self):
        """Default retry policy is configured correctly."""
        policy = RetryPolicy()

        assert policy.max_attempts == 3
        assert policy.backoff_ms == [100, 300, 900]
        assert policy.retryable_status_codes == {502, 503, 504}

    def test_custom_retry_policy(self):
        """Custom retry policy with user-specified values."""
        policy = RetryPolicy(
            max_attempts=5,
            backoff_ms=[50, 100, 200, 400],
            retryable_status_codes={500, 502, 503},
        )

        assert policy.max_attempts == 5
        assert policy.backoff_ms == [50, 100, 200, 400]
        assert policy.retryable_status_codes == {500, 502, 503}

    def test_is_retryable_status(self):
        """Check retryable status code detection."""
        policy = RetryPolicy()

        assert policy.is_retryable_status(502) is True
        assert policy.is_retryable_status(503) is True
        assert policy.is_retryable_status(504) is True
        assert policy.is_retryable_status(400) is False
        assert policy.is_retryable_status(404) is False


class TestHostedClient:
    """Tests for hosted client retry behavior."""

    @pytest.mark.asyncio
    async def test_successful_request_first_try(self):
        """Successful request on first attempt."""
        transport = AsyncMock()
        transport.request.return_value = WorkspaceResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body=b'{"status":"ok"}',
            elapsed_sec=0.1,
            transport_type="http",
        )

        client = HostedClient(transport)
        status, headers, body = await client.request(
            "GET",
            "/internal/v1/files/tree",
            trace_id="trace-123",
        )

        assert status == 200
        assert body == b'{"status":"ok"}'
        assert transport.request.call_count == 1

    @pytest.mark.asyncio
    async def test_request_with_retry_503(self):
        """Request retries on 503 then succeeds."""
        transport = AsyncMock()

        # First call returns 503, second returns 200
        transport.request.side_effect = [
            WorkspaceResponse(
                status_code=503,
                headers={},
                body=b"Service Unavailable",
                elapsed_sec=0.1,
                transport_type="http",
            ),
            WorkspaceResponse(
                status_code=200,
                headers={},
                body=b'{"status":"ok"}',
                elapsed_sec=0.1,
                transport_type="http",
            ),
        ]

        client = HostedClient(transport)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            status, headers, body = await client.request(
                "GET",
                "/internal/v1/files/tree",
            )

        assert status == 200
        assert transport.request.call_count == 2

    @pytest.mark.asyncio
    async def test_request_retries_exhausted(self):
        """Request exhausts retries and fails."""
        transport = AsyncMock()

        # All calls return 502
        transport.request.return_value = WorkspaceResponse(
            status_code=502,
            headers={},
            body=b"Bad Gateway",
            elapsed_sec=0.1,
            transport_type="http",
        )

        client = HostedClient(transport)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(TransportError) as exc_info:
                await client.request("GET", "/internal/v1/files/tree")

        error = exc_info.value
        assert error.code.value == "transport_retry_exhausted"
        assert error.http_status == 502
        assert error.retryable is False
        assert transport.request.call_count == 3  # All 3 attempts

    @pytest.mark.asyncio
    async def test_request_non_retryable_status(self):
        """Non-retryable status code fails immediately."""
        transport = AsyncMock()

        transport.request.return_value = WorkspaceResponse(
            status_code=404,
            headers={},
            body=b"Not Found",
            elapsed_sec=0.1,
            transport_type="http",
        )

        client = HostedClient(transport)

        status, headers, body = await client.request(
            "GET",
            "/internal/v1/files/not-found",
        )

        assert status == 404
        assert transport.request.call_count == 1  # No retries

    @pytest.mark.asyncio
    async def test_trace_id_propagation(self):
        """Trace ID is added to request headers."""
        transport = AsyncMock()

        transport.request.return_value = WorkspaceResponse(
            status_code=200,
            headers={},
            body=b"",
            elapsed_sec=0.1,
            transport_type="http",
        )

        client = HostedClient(transport)

        await client.request(
            "GET",
            "/internal/v1/files/tree",
            trace_id="trace-xyz",
        )

        # Verify trace ID was passed to transport
        call_kwargs = transport.request.call_args[1]
        assert call_kwargs["trace_id"] == "trace-xyz"
        assert call_kwargs["headers"]["X-Trace-ID"] == "trace-xyz"

    @pytest.mark.asyncio
    async def test_backoff_timing(self):
        """Backoff delays increase between retries."""
        transport = AsyncMock()

        # All calls return 502 to trigger retries
        transport.request.return_value = WorkspaceResponse(
            status_code=502,
            headers={},
            body=b"",
            elapsed_sec=0.1,
            transport_type="http",
        )

        policy = RetryPolicy(
            max_attempts=3,
            backoff_ms=[100, 300],
        )
        client = HostedClient(transport, retry_policy=policy)

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(TransportError):
                await client.request("GET", "/path")

        # Should have 2 sleep calls (no sleep after last attempt)
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == 0.1  # 100ms
        assert sleep_calls[1] == 0.3  # 300ms

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Health check delegates to transport."""
        transport = AsyncMock()
        transport.health_check.return_value = HealthStatus.HEALTHY

        client = HostedClient(transport)
        status = await client.health_check(timeout_sec=5.0)

        assert status == HealthStatus.HEALTHY
        transport.health_check.assert_called_once_with(timeout_sec=5.0)

    @pytest.mark.asyncio
    async def test_timeout_error_retryable(self):
        """Timeout errors trigger retry."""
        transport = AsyncMock()

        # First call times out, second succeeds
        transport.request.side_effect = [
            asyncio.TimeoutError(),
            WorkspaceResponse(
                status_code=200,
                headers={},
                body=b"ok",
                elapsed_sec=0.1,
                transport_type="http",
            ),
        ]

        client = HostedClient(transport)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            status, headers, body = await client.request(
                "GET",
                "/internal/v1/files/tree",
            )

        assert status == 200
        assert transport.request.call_count == 2

    @pytest.mark.asyncio
    async def test_custom_retryable_codes(self):
        """Custom retryable status codes are respected."""
        transport = AsyncMock()

        transport.request.side_effect = [
            WorkspaceResponse(
                status_code=400,
                headers={},
                body=b"Bad Request",
                elapsed_sec=0.1,
                transport_type="http",
            ),
            WorkspaceResponse(
                status_code=200,
                headers={},
                body=b"ok",
                elapsed_sec=0.1,
                transport_type="http",
            ),
        ]

        policy = RetryPolicy(
            retryable_status_codes={400, 500},
        )
        client = HostedClient(transport, retry_policy=policy)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            status, headers, body = await client.request(
                "GET",
                "/path",
            )

        assert status == 200
        assert transport.request.call_count == 2  # Retried on 400
