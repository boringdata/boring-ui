"""Observability middleware for FastAPI applications.

Bead: bd-223o.4 (P4)

Provides:
- ``RequestIdMiddleware`` -- generates or accepts ``X-Request-ID`` headers,
  stores the ID in a context variable for structured-log correlation, and
  echoes it on every response.
- ``MetricsMiddleware`` -- increments Prometheus counters and histograms
  for every HTTP request.

Both are ASGI middleware and should be added via ``app.add_middleware()``.
"""

from __future__ import annotations

import re
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .logging import get_logger, request_id_ctx
from .metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_FLIGHT,
    HTTP_REQUESTS_TOTAL,
)

logger = get_logger(__name__)

# Allowed request-ID format: 8-128 chars of hex, dash, or alphanumeric.
_VALID_REQUEST_ID = re.compile(r"^[a-zA-Z0-9\-]{8,128}$")

# Path patterns to normalize for metric labels (avoid high-cardinality).
_PATH_NORMALIZERS = [
    (re.compile(r"/ws/pty/[^/]+"), "/ws/pty/{session}"),
    (re.compile(r"/ws/stream/[^/]+"), "/ws/stream/{session}"),
    (re.compile(r"/api/v1/workspaces/[^/]+"), "/api/v1/workspaces/{id}"),
    (re.compile(r"/api/file\b"), "/api/file"),
]


def _normalize_path(path: str) -> str:
    """Collapse high-cardinality path segments for metric labels."""
    for pattern, replacement in _PATH_NORMALIZERS:
        path = pattern.sub(replacement, path)
    return path


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate or accept X-Request-ID and propagate via contextvars.

    If the incoming request carries a valid X-Request-ID header, it is
    reused. Otherwise, a new UUID is generated. The ID is stored in
    ``request_id_ctx`` so that structlog automatically includes it in
    every log entry during the request.

    Spoofed or malformed IDs are rejected and replaced with a fresh UUID.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        incoming_id = request.headers.get("x-request-id", "")
        if incoming_id and _VALID_REQUEST_ID.match(incoming_id):
            rid = incoming_id
        else:
            rid = str(uuid.uuid4())

        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)

        response.headers["X-Request-ID"] = rid
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record Prometheus HTTP metrics for every request.

    Tracks:
    - ``http_server_requests_total`` by method, normalized path, status
    - ``http_server_request_duration_seconds`` by method, normalized path
    - ``http_server_requests_in_flight`` gauge
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        path = _normalize_path(request.url.path)
        method = request.method

        HTTP_REQUESTS_IN_FLIGHT.inc()
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            HTTP_REQUESTS_TOTAL.labels(
                method=method, path=path, status="500",
            ).inc()
            raise
        finally:
            duration = time.perf_counter() - start
            HTTP_REQUESTS_IN_FLIGHT.dec()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, path=path,
            ).observe(duration)

        HTTP_REQUESTS_TOTAL.labels(
            method=method, path=path, status=str(response.status_code),
        ).inc()

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every completed request with method, path, status, and duration."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response
