"""Sandbox capability token validation middleware.

Provides FastAPI middleware for validating capability tokens issued by the
control plane. Used on the private sandbox API to enforce operation scoping
and prevent unauthorized access.

Architecture:
  1. add_capability_auth_middleware() validates capability tokens
  2. CapabilityAuthContext is injected into request state
  3. Routes check operation permissions using @require_capability
  4. Replay detection prevents token reuse
"""

import time
import logging
from dataclasses import dataclass
from typing import Callable, Any

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse

from .capability_tokens import CapabilityTokenValidator, JTIReplayStore
from .authorization import has_scoped_access

logger = logging.getLogger(__name__)


@dataclass
class CapabilityAuthContext:
    """Capability-based authorization context injected into sandbox requests.

    Available as request.state.capability_context for authorized routes.
    """

    workspace_id: str
    """Target workspace from capability token."""

    operations: set[str]
    """Set of allowed operations from token (e.g., 'files:read', 'git:*')."""

    jti: str
    """Unique token ID for tracking and audit."""

    issued_at: int
    """Token issuance timestamp (iat claim)."""

    expires_at: int
    """Token expiration timestamp (exp claim)."""

    def has_operation(self, operation: str) -> bool:
        """Check if operation is allowed by this capability.

        Supports wildcards:
          'files:*' - has all file operations
          '*' - has all operations

        Args:
            operation: Operation to check (e.g., 'files:read')

        Returns:
            True if operation is allowed, False otherwise
        """
        return has_scoped_access(operation, self.operations)


def add_capability_auth_middleware(
    app: FastAPI,
    validator: CapabilityTokenValidator | None,
    replay_store: JTIReplayStore | None = None,
    required_prefix: str = "/internal/v1",
) -> None:
    """Add capability token validation middleware to FastAPI app.

    Validates incoming capability tokens (from control plane) and injects
    CapabilityAuthContext into request state. Only activates routes under
    the configured prefix (default: /internal/v1).

    Middleware behavior:
      - Skips public routes (those not under required_prefix)
      - Extracts token from Authorization header
      - Validates token signature, claims, and expiry
      - Checks for token replay using JTI cache
      - Injects CapabilityAuthContext into request.state.capability_context
      - Returns 401 for auth failures, 400 for replay attempts

    Args:
        app: FastAPI application
        validator: CapabilityTokenValidator instance (if None, middleware is skipped)
        replay_store: JTIReplayStore for replay detection (created if None)
        required_prefix: URL prefix requiring capability auth (default: /internal/v1)
    """
    if validator is None:
        logger.info("Capability auth middleware disabled (validator not configured)")
        return

    # Create replay store if not provided
    if replay_store is None:
        replay_store = JTIReplayStore()

    @app.middleware("http")
    async def capability_auth(request: Request, call_next: Callable) -> Any:
        # Skip auth for routes outside protected prefix
        if not request.url.path.startswith(required_prefix):
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.debug(
                f"Missing Bearer token for capability auth: {request.method} {request.url.path}"
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Missing or invalid authorization header",
                    "code": "CAP_AUTH_MISSING",
                },
                headers={"WWW-Authenticate": 'Bearer realm="boring-ui-sandbox"'},
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Validate token
        claims = validator.validate_token(token)
        if claims is None:
            logger.debug(
                f"Invalid capability token: {request.method} {request.url.path}"
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid or expired capability token",
                    "code": "CAP_AUTH_INVALID",
                },
                headers={
                    "WWW-Authenticate": 'Bearer realm="boring-ui-sandbox", error="invalid_token"'
                },
            )

        # Get JTI for replay detection
        jti = claims.get("jti")
        if not jti:
            logger.warning("Capability token missing jti claim")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid token structure (missing jti)",
                    "code": "CAP_AUTH_INVALID_CLAIMS",
                },
            )

        # Check for replay attack
        if replay_store.is_replayed(jti):
            logger.warning(f"Capability token replay detected: jti={jti}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "detail": "Capability token has already been used (replay detected)",
                    "code": "CAP_REPLAY_DETECTED",
                    "jti": jti,
                },
            )

        # Record JTI to prevent future replay using remaining lifetime
        now = int(time.time())
        exp = claims.get("exp", 0)
        remaining_ttl = exp - now
        # Only record if token has remaining lifetime (avoid cache pollution with zero-TTL entries)
        if remaining_ttl > 0:
            replay_store.record_jti(jti, remaining_ttl)

        # Create and inject capability context
        capability_context = CapabilityAuthContext(
            workspace_id=claims.get("workspace_id", ""),
            operations=set(claims.get("ops", [])),
            jti=jti,
            issued_at=claims.get("iat", 0),
            expires_at=claims.get("exp", 0),
        )
        request.state.capability_context = capability_context

        logger.debug(
            f"Capability context injected: workspace={capability_context.workspace_id}, "
            f"ops={len(capability_context.operations)}, jti={jti}"
        )

        return await call_next(request)

    logger.info(f"Capability auth middleware added (requires: {required_prefix})")


def get_capability_context(request: Request) -> CapabilityAuthContext:
    """Extract CapabilityAuthContext from request state.

    Use this in route handlers to access capability-based authorization context.

    Args:
        request: FastAPI Request object

    Returns:
        CapabilityAuthContext with workspace, operations, and JTI

    Raises:
        HTTPException: 401 if not authenticated via capability token
    """
    capability_context = getattr(request.state, "capability_context", None)
    if capability_context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Capability token required",
        )
    return capability_context


def require_capability(operation: str):
    """Decorator to require a specific operation for a route.

    Usage:
        @app.post("/internal/v1/files/read")
        @require_capability("files:read")
        async def read_file(request: Request):
            ...

    Args:
        operation: Operation required (e.g., "files:read", "git:status")

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        import inspect
        from functools import wraps

        # Preserve function metadata
        @wraps(func)
        async def async_wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            capability_context = get_capability_context(request)
            if not capability_context.has_operation(operation):
                logger.warning(
                    f"Operation denied: jti={capability_context.jti}, "
                    f"required={operation}, allowed={capability_context.operations}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Operation not allowed: {operation}",
                    headers={
                        "X-Capability-Code": f"OP_DENIED:{operation}",
                        "X-JTI": capability_context.jti,
                    },
                )
            return await func(request, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            capability_context = get_capability_context(request)
            if not capability_context.has_operation(operation):
                logger.warning(
                    f"Operation denied: jti={capability_context.jti}, "
                    f"required={operation}, allowed={capability_context.operations}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Operation not allowed: {operation}",
                    headers={
                        "X-Capability-Code": f"OP_DENIED:{operation}",
                        "X-JTI": capability_context.jti,
                    },
                )
            return func(request, *args, **kwargs)

        # Check if original function is async and use appropriate wrapper
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
