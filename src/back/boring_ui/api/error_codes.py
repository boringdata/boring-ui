"""Structured error codes for workspace transport and control-plane operations (bd-1adh.4.2).

Provides stable, machine-readable error codes for transport failures, timeouts,
and protocol violations. Enables deterministic error handling and observability.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ErrorCode(str, Enum):
    """Workspace transport error codes."""

    # Sprites-specific transport errors
    SPRITES_HANDSHAKE_TIMEOUT = "sprites_handshake_timeout"
    SPRITES_HANDSHAKE_INVALID = "sprites_handshake_invalid"
    SPRITES_RELAY_LOST = "sprites_relay_lost"
    SPRITES_CONNECT_TIMEOUT = "sprites_connect_timeout"

    # Local API errors
    LOCAL_API_UNAVAILABLE = "local_api_unavailable"
    LOCAL_API_TIMEOUT = "local_api_timeout"
    LOCAL_API_PROTOCOL_ERROR = "local_api_protocol_error"

    # Generic transport errors
    TRANSPORT_RETRY_EXHAUSTED = "transport_retry_exhausted"
    TRANSPORT_PARSE_ERROR = "transport_parse_error"
    TRANSPORT_SIZE_EXCEEDED = "transport_size_exceeded"

    # Request validation
    INVALID_REQUEST_HEADERS = "invalid_request_headers"
    INVALID_REQUEST_BODY = "invalid_request_body"

    # HTTP protocol errors
    HTTP_STATUS_400 = "http_400_bad_request"
    HTTP_STATUS_401 = "http_401_unauthorized"
    HTTP_STATUS_403 = "http_403_forbidden"
    HTTP_STATUS_404 = "http_404_not_found"
    HTTP_STATUS_500 = "http_500_internal_error"
    HTTP_STATUS_502 = "http_502_bad_gateway"
    HTTP_STATUS_503 = "http_503_unavailable"
    HTTP_STATUS_504 = "http_504_gateway_timeout"


@dataclass
class TransportError:
    """Represents a transport-level error with code and details.

    Attributes:
        code: ErrorCode enum value
        message: Human-readable error message
        http_status: HTTP status code to return to client
        retryable: Whether the error is retryable
        details: Optional additional error context
    """
    code: ErrorCode
    message: str
    http_status: int
    retryable: bool
    details: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dict for API responses."""
        return {
            "error_code": self.code.value,
            "message": self.message,
            "http_status": self.http_status,
            "retryable": self.retryable,
            "details": self.details or {},
        }


# Error mapping utilities

def map_sprites_connect_error(
    error: Exception,
    elapsed_sec: float,
) -> TransportError:
    """Map Sprites connection error to TransportError.

    Args:
        error: Exception from connection attempt
        elapsed_sec: Time elapsed before error

    Returns:
        TransportError with appropriate code and status
    """
    if isinstance(error, TimeoutError):
        return TransportError(
            code=ErrorCode.SPRITES_CONNECT_TIMEOUT,
            message=f"Sprites proxy connection timeout after {elapsed_sec:.1f}s",
            http_status=502,
            retryable=True,
            details={"elapsed_sec": elapsed_sec},
        )
    else:
        return TransportError(
            code=ErrorCode.SPRITES_RELAY_LOST,
            message=f"Sprites proxy connection failed: {str(error)}",
            http_status=502,
            retryable=True,
            details={"error": str(error), "elapsed_sec": elapsed_sec},
        )


def map_sprites_handshake_error(
    error: Exception,
    elapsed_sec: float,
) -> TransportError:
    """Map Sprites handshake error to TransportError.

    Args:
        error: Exception during handshake
        elapsed_sec: Time elapsed before error

    Returns:
        TransportError with appropriate code and status
    """
    if isinstance(error, TimeoutError):
        return TransportError(
            code=ErrorCode.SPRITES_HANDSHAKE_TIMEOUT,
            message=f"Sprites proxy handshake timeout after {elapsed_sec:.1f}s",
            http_status=502,
            retryable=True,
            details={"elapsed_sec": elapsed_sec},
        )
    else:
        return TransportError(
            code=ErrorCode.SPRITES_HANDSHAKE_INVALID,
            message=f"Sprites proxy handshake failed: {str(error)}",
            http_status=502,
            retryable=False,
            details={"error": str(error)},
        )


def map_relay_timeout_error(
    elapsed_sec: float,
) -> TransportError:
    """Map relay timeout error to TransportError.

    Args:
        elapsed_sec: Time elapsed before timeout

    Returns:
        TransportError with appropriate code and status
    """
    return TransportError(
        code=ErrorCode.SPRITES_RELAY_LOST,
        message=f"Sprites relay timeout after {elapsed_sec:.1f}s",
        http_status=504,
        retryable=True,
        details={"elapsed_sec": elapsed_sec},
    )


def map_protocol_parse_error(
    error: Exception,
    reason: str,
) -> TransportError:
    """Map HTTP protocol parse error to TransportError.

    Args:
        error: Exception from parsing
        reason: Description of what failed to parse

    Returns:
        TransportError with appropriate code and status
    """
    return TransportError(
        code=ErrorCode.LOCAL_API_PROTOCOL_ERROR,
        message=f"HTTP response parse error: {reason}",
        http_status=502,
        retryable=False,
        details={"error": str(error), "reason": reason},
    )


def map_size_exceeded_error(
    actual_bytes: int,
    max_bytes: int,
) -> TransportError:
    """Map response size exceeded error to TransportError.

    Args:
        actual_bytes: Actual response size
        max_bytes: Maximum allowed size

    Returns:
        TransportError with appropriate code and status
    """
    return TransportError(
        code=ErrorCode.TRANSPORT_SIZE_EXCEEDED,
        message=f"Response exceeded size limit: {actual_bytes} > {max_bytes}",
        http_status=502,
        retryable=False,
        details={
            "actual_bytes": actual_bytes,
            "max_bytes": max_bytes,
        },
    )


def map_http_status_to_error(status_code: int) -> TransportError:
    """Map HTTP status code to TransportError.

    Args:
        status_code: HTTP status code from local-api

    Returns:
        TransportError preserving the original status
    """
    # Retryable 5xx errors
    if status_code == 502:
        return TransportError(
            code=ErrorCode.HTTP_STATUS_502,
            message="Local API returned 502 Bad Gateway",
            http_status=502,
            retryable=True,
        )
    elif status_code == 503:
        return TransportError(
            code=ErrorCode.HTTP_STATUS_503,
            message="Local API returned 503 Service Unavailable",
            http_status=503,
            retryable=True,
        )
    elif status_code == 504:
        return TransportError(
            code=ErrorCode.HTTP_STATUS_504,
            message="Local API returned 504 Gateway Timeout",
            http_status=504,
            retryable=True,
        )
    elif status_code in (500,):
        return TransportError(
            code=ErrorCode.HTTP_STATUS_500,
            message="Local API returned 500 Internal Server Error",
            http_status=500,
            retryable=True,
        )

    # Non-retryable client errors
    elif status_code == 400:
        return TransportError(
            code=ErrorCode.HTTP_STATUS_400,
            message="Local API returned 400 Bad Request",
            http_status=400,
            retryable=False,
        )
    elif status_code == 401:
        return TransportError(
            code=ErrorCode.HTTP_STATUS_401,
            message="Local API returned 401 Unauthorized",
            http_status=401,
            retryable=False,
        )
    elif status_code == 403:
        return TransportError(
            code=ErrorCode.HTTP_STATUS_403,
            message="Local API returned 403 Forbidden",
            http_status=403,
            retryable=False,
        )
    elif status_code == 404:
        return TransportError(
            code=ErrorCode.HTTP_STATUS_404,
            message="Local API returned 404 Not Found",
            http_status=404,
            retryable=False,
        )

    # Default for other status codes
    else:
        return TransportError(
            code=ErrorCode.LOCAL_API_UNAVAILABLE,
            message=f"Local API returned status {status_code}",
            http_status=status_code,
            retryable=(500 <= status_code < 600),
        )
