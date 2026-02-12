"""Hosted client for control-plane to workspace plane communication with retry policy (bd-1adh.4.3).

Implements retry/backoff strategy with trace ID propagation for reliable
communication through Sprites proxy or HTTP transport.
"""

from dataclasses import dataclass
import asyncio
import logging
from typing import Optional
from boring_ui.api.transport import (
    WorkspaceTransport,
    HealthStatus,
)
from boring_ui.api.error_codes import (
    ErrorCode,
    TransportError,
)


logger = logging.getLogger(__name__)


@dataclass
class RetryPolicy:
    """Retry policy configuration.

    Attributes:
        max_attempts: Maximum number of retry attempts
        backoff_ms: List of backoff times in milliseconds for each retry
        retryable_status_codes: HTTP status codes that trigger retry
    """
    max_attempts: int = 3
    backoff_ms: list[int] | None = None
    retryable_status_codes: set[int] | None = None

    def __post_init__(self):
        """Initialize defaults."""
        if self.backoff_ms is None:
            # Default exponential backoff: 100ms, 300ms, 900ms
            self.backoff_ms = [100, 300, 900]
        if self.retryable_status_codes is None:
            # Retryable: 502, 503, 504
            self.retryable_status_codes = {502, 503, 504}

    def is_retryable_status(self, status_code: int) -> bool:
        """Check if status code is retryable.

        Args:
            status_code: HTTP status code

        Returns:
            True if the status code should trigger retry
        """
        return status_code in self.retryable_status_codes


class HostedClient:
    """Client for hosted control-plane operations with retry semantics (bd-1adh.4.3).

    Wraps WorkspaceTransport with deterministic retry/backoff and trace propagation.
    """

    def __init__(
        self,
        transport: WorkspaceTransport,
        retry_policy: RetryPolicy | None = None,
    ):
        """Initialize hosted client.

        Args:
            transport: Workspace transport implementation
            retry_policy: Optional retry configuration (uses defaults if not provided)
        """
        self.transport = transport
        self.retry_policy = retry_policy or RetryPolicy()

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: float = 30.0,
        trace_id: str | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Send request with automatic retry on transient failures.

        Args:
            method: HTTP method
            path: URL path
            body: Optional body
            headers: Optional headers
            timeout_sec: Request timeout
            trace_id: Trace ID for observability

        Returns:
            Tuple of (status_code, headers, body)

        Raises:
            TransportError: On permanent or exhausted retries
            asyncio.TimeoutError: On timeout
        """
        last_error: Optional[Exception] = None
        req_headers = headers or {}

        # Add trace ID if provided
        if trace_id:
            req_headers["X-Trace-ID"] = trace_id

        for attempt in range(self.retry_policy.max_attempts):
            try:
                logger.debug(
                    f"Hosted request attempt {attempt + 1}/{self.retry_policy.max_attempts}",
                    extra={
                        "trace_id": trace_id,
                        "method": method,
                        "path": path,
                        "attempt": attempt + 1,
                    },
                )

                response = await self.transport.request(
                    method,
                    path,
                    body=body,
                    headers=req_headers,
                    timeout_sec=timeout_sec,
                    trace_id=trace_id,
                )

                # Check for retryable status codes
                if self.retry_policy.is_retryable_status(response.status_code):
                    if attempt < self.retry_policy.max_attempts - 1:
                        # Retry on transient error
                        backoff_ms = self.retry_policy.backoff_ms[attempt]
                        logger.warning(
                            f"Retryable status {response.status_code}, backing off {backoff_ms}ms",
                            extra={"trace_id": trace_id, "attempt": attempt + 1},
                        )
                        await asyncio.sleep(backoff_ms / 1000.0)
                        continue
                    else:
                        # Last attempt, exhausted retries
                        logger.error(
                            f"Retries exhausted on status {response.status_code}",
                            extra={"trace_id": trace_id},
                        )
                        raise TransportError(
                            code=ErrorCode.TRANSPORT_RETRY_EXHAUSTED,
                            message=f"All {self.retry_policy.max_attempts} retries exhausted, last status: {response.status_code}",
                            http_status=response.status_code,
                            retryable=False,
                            details={"attempts": self.retry_policy.max_attempts},
                        )

                # Non-retryable response
                logger.debug(
                    f"Hosted request success: status {response.status_code}",
                    extra={"trace_id": trace_id},
                )
                return response.status_code, response.headers, response.body

            except (asyncio.TimeoutError, Exception) as e:
                last_error = e

                # Check if this is a retryable error
                is_timeout = isinstance(e, asyncio.TimeoutError)
                should_retry = is_timeout or (
                    isinstance(e, Exception) and hasattr(e, "retryable") and e.retryable
                )

                if should_retry and attempt < self.retry_policy.max_attempts - 1:
                    backoff_ms = self.retry_policy.backoff_ms[attempt]
                    logger.warning(
                        f"Transient error on attempt {attempt + 1}, backing off {backoff_ms}ms",
                        extra={
                            "trace_id": trace_id,
                            "error": str(e),
                            "attempt": attempt + 1,
                        },
                    )
                    await asyncio.sleep(backoff_ms / 1000.0)
                    continue
                else:
                    # Non-retryable or last attempt
                    logger.error(
                        f"Request failed with non-retryable error: {e}",
                        extra={"trace_id": trace_id, "attempt": attempt + 1},
                    )
                    raise

        # Should not reach here, but just in case
        raise last_error or Exception("Unknown error in hosted client")

    async def health_check(self, timeout_sec: float = 5.0) -> HealthStatus:
        """Check transport health.

        Args:
            timeout_sec: Health check timeout

        Returns:
            HealthStatus enum value
        """
        return await self.transport.health_check(timeout_sec=timeout_sec)
