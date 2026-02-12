"""Request correlation ID propagation for sandbox mode.

Generates and propagates a unique request_id through:
  - Inbound HTTP requests (from browser or upstream)
  - Outbound proxy requests (to workspace service)
  - WebSocket connections (PTY, chat)
  - Log records (via ContextVar)

The request_id flows through the entire request lifecycle for
debuggable traces across control plane, workspace service, and
exec interactions.
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Header names for request correlation.
REQUEST_ID_HEADER = 'X-Request-ID'
UPSTREAM_REQUEST_ID_HEADER = 'X-Upstream-Request-ID'

# ContextVar for accessing request_id in any async context.
current_request_id: ContextVar[str] = ContextVar('current_request_id', default='')


def generate_request_id() -> str:
    """Generate a new unique request ID."""
    return str(uuid.uuid4())


def get_or_create_request_id(request_id: str | None = None) -> str:
    """Return the provided request_id or generate a new one."""
    if request_id and request_id.strip():
        return request_id.strip()
    return generate_request_id()


def extract_request_id(headers: dict[str, str]) -> str | None:
    """Extract request ID from headers (case-insensitive)."""
    for key, value in headers.items():
        if key.lower() == REQUEST_ID_HEADER.lower():
            return value.strip() if value else None
    return None


def inject_request_id(
    headers: dict[str, str],
    request_id: str,
    *,
    as_upstream: bool = False,
) -> dict[str, str]:
    """Add request ID to outbound headers.

    Args:
        headers: Existing headers dict.
        request_id: The request ID to inject.
        as_upstream: If True, use X-Upstream-Request-ID for proxy hops.

    Returns:
        New headers dict with request ID added.
    """
    result = dict(headers)
    result[REQUEST_ID_HEADER] = request_id
    if as_upstream:
        result[UPSTREAM_REQUEST_ID_HEADER] = request_id
    return result


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that ensures every request has a correlation ID.

    - Reads X-Request-ID from inbound request if present.
    - Generates a new ID if not present.
    - Sets the ContextVar for downstream access.
    - Adds X-Request-ID to the response.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        trust_incoming: bool = False,
    ):
        """
        Args:
            app: ASGI application.
            trust_incoming: If True, trust client-provided X-Request-ID.
                If False, always generate a new ID (safer for untrusted clients).
        """
        super().__init__(app)
        self.trust_incoming = trust_incoming

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ):
        incoming_id = request.headers.get(REQUEST_ID_HEADER)

        if self.trust_incoming and incoming_id:
            request_id = incoming_id.strip()
        else:
            request_id = generate_request_id()

        # Set the ContextVar for downstream access.
        token = current_request_id.set(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            current_request_id.reset(token)


class CorrelationLogFilter(logging.Filter):
    """Logging filter that adds request_id to log records.

    Usage:
        handler.addFilter(CorrelationLogFilter())
        # In format string: %(request_id)s
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id.get('')  # type: ignore[attr-defined]
        return True
