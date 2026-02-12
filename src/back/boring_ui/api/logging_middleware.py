"""Structured logging and request correlation middleware (bd-1pwb.9.1).

Provides:
- Request-ID generation and propagation for end-to-end tracing
- Structured logging with correlation fields
- Cross-service trace correlation (sandbox, companion)
- Performance instrumentation (latency tracking)
"""

import logging
import time
import uuid
import json
from typing import Callable, Any
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


# Structured logger for JSON-formatted logs
def _configure_structured_logging():
    """Configure Python logging for structured output."""
    # Get root logger
    logger = logging.getLogger()

    # Check if already configured
    if logger.handlers and any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        return

    # Remove default handlers
    logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler()

    # Use JSON formatter for structured logs
    class JSONFormatter(logging.Formatter):
        """Format logs as JSON with standard fields."""

        def format(self, record: logging.LogRecord) -> str:
            # Format timestamp with milliseconds
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
            timestamp = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"  # Remove microseconds to ms

            log_data = {
                "timestamp": timestamp,
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }

            # Add optional fields if present
            if hasattr(record, "request_id") and record.request_id:
                log_data["request_id"] = record.request_id
            if hasattr(record, "user_id") and record.user_id:
                log_data["user_id"] = record.user_id
            if hasattr(record, "method") and record.method:
                log_data["method"] = record.method
            if hasattr(record, "path") and record.path:
                log_data["path"] = record.path
            if hasattr(record, "status") and record.status:
                log_data["status"] = record.status
            if hasattr(record, "latency_ms") and record.latency_ms:
                log_data["latency_ms"] = record.latency_ms

            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            return json.dumps(log_data, default=str)

    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware for request-ID generation and propagation.

    - Generates unique request_id (UUID) for each request
    - Attaches to request.state.request_id
    - Includes in response headers (X-Request-ID)
    - Available to all downstream handlers

    Usage in routes:
        async def my_route(request: Request):
            request_id = request.state.request_id
            # Use request_id in logging, audit, etc.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or use existing request_id
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Track request start time for latency
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Add request_id to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{latency_ms:.2f}ms"

        return response


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging.

    Logs all HTTP requests with structured fields:
    - request_id (from request.state)
    - method, path, status_code
    - latency_ms
    - user_id (if authenticated)

    Logs are emitted at INFO level for normal requests,
    WARNING for errors, and DEBUG for internal/health endpoints.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        logger = logging.getLogger("boring_ui.http")

        # Extract request_id if already set by RequestIDMiddleware
        request_id = getattr(request.state, "request_id", None)

        # Extract user_id if authenticated
        user_id = None
        auth_context = getattr(request.state, "auth_context", None)
        if auth_context:
            user_id = auth_context.user_id

        # Track timing
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        self._record_operation_metrics(request.url.path, latency_ms, response.status_code)

        # Build log record with structured fields
        log_record = logger.makeRecord(
            name=logger.name,
            level=logging.INFO,
            fn=__file__,
            lno=0,
            msg=f"{request.method} {request.url.path} -> {response.status_code}",
            args=(),
            exc_info=None,
        )

        # Attach structured fields
        log_record.request_id = request_id
        log_record.method = request.method
        log_record.path = request.url.path
        log_record.status = response.status_code
        log_record.latency_ms = latency_ms
        if user_id:
            log_record.user_id = user_id

        # Determine log level based on status and path
        if request.url.path in ("/health", "/api/health"):
            # Skip logging for health checks (use DEBUG if needed)
            pass
        elif response.status_code >= 500:
            log_record.levelno = logging.ERROR
        elif response.status_code >= 400:
            log_record.levelno = logging.WARNING
        else:
            log_record.levelno = logging.INFO

        # Log the request
        logger.handle(log_record)

        return response

    @staticmethod
    def _record_operation_metrics(path: str, latency_ms: float, status_code: int) -> None:
        """Record canonical operation metrics from request path (disabled - observability removed)."""
        pass


def add_logging_middleware(app: FastAPI) -> None:
    """Add structured logging and request correlation middleware to app.

    Must be added early in middleware stack (before other middlewares that
    may use request_id for correlation).

    Order matters:
    1. RequestIDMiddleware - generates request_id
    2. StructuredLoggingMiddleware - logs with request_id
    3. Other middlewares (auth, etc.)

    Args:
        app: FastAPI application
    """
    # Configure Python logging for structured output
    _configure_structured_logging()

    # Add middleware in order (inner-most first)
    # RequestIDMiddleware is the inner-most to generate request_id first
    app.add_middleware(StructuredLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    logger = logging.getLogger(__name__)
    logger.info("Structured logging middleware added (bd-1pwb.9.1)")


def get_request_id(request: Request) -> str:
    """Extract request_id from request state.

    Use this in route handlers to get the current request's correlation ID.

    Args:
        request: FastAPI Request object

    Returns:
        Request ID (UUID string)
    """
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def propagate_request_context(
    request: Request, headers: dict | None = None
) -> dict[str, str]:
    """Build headers to propagate request context to subservices.

    Use this when making outbound requests to sandbox, companion,
    or other services to maintain trace correlation end-to-end.

    Args:
        request: FastAPI Request object
        headers: Base headers dict to augment (optional)

    Returns:
        Headers dict with X-Request-ID and optionally X-User-ID set
    """
    if headers is None:
        headers = {}

    # Always propagate request_id for trace correlation
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id

    # Propagate user_id if authenticated
    auth_context = getattr(request.state, "auth_context", None)
    if auth_context:
        headers["X-User-ID"] = auth_context.user_id
        if auth_context.workspace_id:
            headers["X-Workspace-ID"] = auth_context.workspace_id

    return headers
