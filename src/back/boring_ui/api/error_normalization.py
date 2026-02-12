"""Cross-client error normalization for sandbox mode.

Maps upstream provider/service failures into stable, browser-safe HTTP
and WebSocket semantics without leaking provider internals.

Goals:
  1. No internal service names, URLs, or stack traces reach the browser.
  2. Every upstream failure maps to a known browser-visible error shape.
  3. WebSocket close codes are standardized across providers.
  4. Errors are logged with full detail server-side for debugging.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


# ── Error categories ──


class ErrorCategory(Enum):
    """High-level error categories for normalization."""
    VALIDATION = 'validation'
    NOT_FOUND = 'not_found'
    CONFLICT = 'conflict'
    AUTH = 'auth'
    RATE_LIMIT = 'rate_limit'
    PROVIDER_ERROR = 'provider_error'
    PROVIDER_UNAVAILABLE = 'provider_unavailable'
    PROVIDER_TIMEOUT = 'provider_timeout'
    TRANSPORT = 'transport'
    INTERNAL = 'internal'


# ── Normalized error ──


@dataclass(frozen=True)
class NormalizedError:
    """A normalized error ready for browser consumption.

    Fields:
      category: High-level error type for programmatic handling
      http_status: HTTP status code for the browser response
      message: Safe, human-readable error message
      ws_close_code: WebSocket close code (if applicable)
      retry_after: Seconds the client should wait before retrying (0 = no retry)
    """
    category: ErrorCategory
    http_status: int
    message: str
    ws_close_code: int = 0
    retry_after: int = 0


# ── Standard WS close codes ──

WS_NORMAL_CLOSURE = 1000
WS_GOING_AWAY = 1001
WS_PROTOCOL_ERROR = 1002
WS_INTERNAL_ERROR = 1011

# Application-specific close codes (4000-4999)
WS_SESSION_NOT_FOUND = 4001
WS_SESSION_TERMINATED = 4002
WS_PROVIDER_UNKNOWN = 4003
WS_VALIDATION_ERROR = 4004
WS_RATE_LIMITED = 4005
WS_PROVIDER_UNAVAILABLE = 4006
WS_PROVIDER_TIMEOUT = 4007
WS_AUTH_REQUIRED = 4008


# ── Error normalization rules ──


# HTTP error map: upstream condition -> NormalizedError
_HTTP_ERROR_MAP: dict[str, NormalizedError] = {
    # Client errors - pass through with safe messages
    'bad_request': NormalizedError(
        category=ErrorCategory.VALIDATION,
        http_status=400,
        message='Invalid request',
    ),
    'not_found': NormalizedError(
        category=ErrorCategory.NOT_FOUND,
        http_status=404,
        message='Resource not found',
    ),
    'conflict': NormalizedError(
        category=ErrorCategory.CONFLICT,
        http_status=409,
        message='Resource conflict',
    ),
    'validation_error': NormalizedError(
        category=ErrorCategory.VALIDATION,
        http_status=422,
        message='Validation error',
    ),
    'unauthorized': NormalizedError(
        category=ErrorCategory.AUTH,
        http_status=403,
        message='Authentication required',
    ),
    'rate_limited': NormalizedError(
        category=ErrorCategory.RATE_LIMIT,
        http_status=429,
        message='Rate limit exceeded',
        retry_after=60,
    ),
    # Provider errors - map to generic upstream errors
    'provider_error': NormalizedError(
        category=ErrorCategory.PROVIDER_ERROR,
        http_status=502,
        message='Service temporarily unavailable',
    ),
    'provider_unavailable': NormalizedError(
        category=ErrorCategory.PROVIDER_UNAVAILABLE,
        http_status=503,
        message='Service temporarily unavailable',
        retry_after=5,
    ),
    'provider_timeout': NormalizedError(
        category=ErrorCategory.PROVIDER_TIMEOUT,
        http_status=504,
        message='Request timed out',
    ),
    'transport_error': NormalizedError(
        category=ErrorCategory.TRANSPORT,
        http_status=502,
        message='Service communication error',
    ),
    'internal_error': NormalizedError(
        category=ErrorCategory.INTERNAL,
        http_status=500,
        message='Internal server error',
    ),
}

# WebSocket close code map
_WS_ERROR_MAP: dict[str, NormalizedError] = {
    'session_not_found': NormalizedError(
        category=ErrorCategory.NOT_FOUND,
        http_status=404,
        message='Session not found',
        ws_close_code=WS_SESSION_NOT_FOUND,
    ),
    'session_terminated': NormalizedError(
        category=ErrorCategory.NOT_FOUND,
        http_status=410,
        message='Session terminated',
        ws_close_code=WS_SESSION_TERMINATED,
    ),
    'provider_unknown': NormalizedError(
        category=ErrorCategory.VALIDATION,
        http_status=400,
        message='Unknown provider',
        ws_close_code=WS_PROVIDER_UNKNOWN,
    ),
    'ws_validation_error': NormalizedError(
        category=ErrorCategory.VALIDATION,
        http_status=400,
        message='Invalid WebSocket message',
        ws_close_code=WS_VALIDATION_ERROR,
    ),
    'ws_rate_limited': NormalizedError(
        category=ErrorCategory.RATE_LIMIT,
        http_status=429,
        message='WebSocket rate limit exceeded',
        ws_close_code=WS_RATE_LIMITED,
        retry_after=60,
    ),
    'ws_provider_unavailable': NormalizedError(
        category=ErrorCategory.PROVIDER_UNAVAILABLE,
        http_status=503,
        message='Provider unavailable',
        ws_close_code=WS_PROVIDER_UNAVAILABLE,
        retry_after=5,
    ),
    'ws_provider_timeout': NormalizedError(
        category=ErrorCategory.PROVIDER_TIMEOUT,
        http_status=504,
        message='Provider timeout',
        ws_close_code=WS_PROVIDER_TIMEOUT,
    ),
    'ws_auth_required': NormalizedError(
        category=ErrorCategory.AUTH,
        http_status=403,
        message='Authentication required',
        ws_close_code=WS_AUTH_REQUIRED,
    ),
}


def normalize_http_error(
    error_key: str,
    *,
    internal_detail: str = '',
    request_id: str = '',
) -> NormalizedError:
    """Normalize an upstream HTTP error to a browser-safe response.

    Args:
        error_key: Error identifier (e.g., 'provider_error', 'not_found')
        internal_detail: Detailed error for server-side logging (never sent to browser)
        request_id: Correlation ID for log linking

    Returns:
        NormalizedError with browser-safe status and message
    """
    normalized = _HTTP_ERROR_MAP.get(error_key)
    if normalized is None:
        logger.warning(
            'Unknown HTTP error key %r (request_id=%s, detail=%s)',
            error_key, request_id, internal_detail,
        )
        normalized = _HTTP_ERROR_MAP['internal_error']

    if internal_detail:
        logger.error(
            'Normalized %s -> %d (request_id=%s, internal=%s)',
            error_key, normalized.http_status, request_id, internal_detail,
        )

    return normalized


def normalize_ws_error(
    error_key: str,
    *,
    internal_detail: str = '',
    request_id: str = '',
) -> NormalizedError:
    """Normalize a WebSocket error to a browser-safe close code and message.

    Args:
        error_key: Error identifier (e.g., 'session_not_found', 'ws_rate_limited')
        internal_detail: Detailed error for server-side logging
        request_id: Correlation ID

    Returns:
        NormalizedError with ws_close_code set
    """
    normalized = _WS_ERROR_MAP.get(error_key)
    if normalized is None:
        logger.warning(
            'Unknown WS error key %r (request_id=%s, detail=%s)',
            error_key, request_id, internal_detail,
        )
        normalized = NormalizedError(
            category=ErrorCategory.INTERNAL,
            http_status=500,
            message='Internal error',
            ws_close_code=WS_INTERNAL_ERROR,
        )

    if internal_detail:
        logger.error(
            'Normalized WS %s -> %d (request_id=%s, internal=%s)',
            error_key, normalized.ws_close_code, request_id, internal_detail,
        )

    return normalized


def normalize_http_status(upstream_status: int) -> NormalizedError:
    """Normalize an upstream HTTP status code to a browser-safe error.

    Convenience function that maps raw status codes to error keys.
    """
    status_map = {
        400: 'bad_request',
        401: 'unauthorized',
        403: 'unauthorized',
        404: 'not_found',
        409: 'conflict',
        422: 'validation_error',
        429: 'rate_limited',
        500: 'provider_error',
        502: 'provider_error',
        503: 'provider_unavailable',
        504: 'provider_timeout',
    }
    key = status_map.get(upstream_status, 'internal_error')
    if upstream_status >= 500 and upstream_status not in status_map:
        key = 'provider_error'
    return normalize_http_error(key)


def error_response_body(normalized: NormalizedError) -> dict:
    """Build a JSON error response body from a NormalizedError.

    The body is safe for browser consumption with no internal details.
    """
    body: dict = {
        'error': normalized.message,
        'category': normalized.category.value,
    }
    if normalized.retry_after > 0:
        body['retry_after'] = normalized.retry_after
    return body
