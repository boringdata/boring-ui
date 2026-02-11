"""Authentication and authorization middleware for hosted mode.

Provides FastAPI middleware stack for JWT validation, auth context injection,
and permission enforcement. Designed for hosted deployments where frontend
auth is handled by an external OIDC provider (Auth0, Cognito, etc).

Architecture:
  1. add_oidc_auth_middleware() validates JWT and injects AuthContext
  2. AuthContext is available as request.state.auth_context
  3. Permission checks use AuthContext to enforce workspace/operation ACLs
  4. Consistent error semantics: 401 (invalid), 403 (insufficient permissions)
"""

import logging
from dataclasses import dataclass, field
from typing import Callable, Any

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse

from .auth import OIDCVerifier

logger = logging.getLogger(__name__)


@dataclass
class AuthContext:
    """Authentication and authorization context injected into requests.

    Available as request.state.auth_context for authorized routes.
    """

    # User identity
    user_id: str
    """Subject (user ID) from JWT 'sub' claim."""

    # Workspace context
    workspace_id: str | None = None
    """Workspace ID from JWT 'workspace' claim or configured default."""

    # Authorization
    permissions: set[str] = field(default_factory=set)
    """Set of permission strings (e.g., 'files:read', 'git:*', 'exec:exec')."""

    # Token data
    claims: dict[str, Any] = field(default_factory=dict)
    """Full JWT payload for inspection (read-only in production)."""

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission.

        Supports wildcards:
          'git:*' - has all git permissions
          '*' - has all permissions

        Args:
            permission: Permission string to check

        Returns:
            True if user has this permission
        """
        # Exact match
        if permission in self.permissions:
            return True

        # Wildcard checks
        if "*" in self.permissions:
            return True

        # Check namespace wildcards (e.g., 'git:*' matches 'git:read')
        namespace = permission.split(":")[0] + ":*"
        if namespace in self.permissions:
            return True

        return False


def add_oidc_auth_middleware(app: FastAPI, verifier: OIDCVerifier | None) -> None:
    """Add OIDC authentication middleware to FastAPI app.

    Validates incoming JWTs against configured OIDC provider and injects
    AuthContext into request state. Only activates if OIDC is configured
    and run mode is HOSTED.

    Middleware behavior:
      - Extracts Bearer token from Authorization header
      - Validates JWT using OIDCVerifier
      - Injects AuthContext into request.state.auth_context
      - Returns 401 if invalid/missing token
      - Allows request to proceed (downstream routes check permissions)

    Args:
        app: FastAPI application
        verifier: OIDCVerifier instance (if None, middleware is skipped)
    """
    if verifier is None:
        logger.info("OIDC auth middleware disabled (OIDC not configured)")
        return

    @app.middleware("http")
    async def oidc_auth(request: Request, call_next: Callable) -> Any:
        # Public health check endpoint
        if request.url.path == "/health":
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            # No token provided
            logger.debug(f"Missing Bearer token: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Missing or invalid authorization header",
                    "code": "AUTH_MISSING",
                },
                headers={"WWW-Authenticate": 'Bearer realm="boring-ui"'},
            )

        token = auth_header[7:]  # Remove "Bearer " prefix

        # Validate JWT
        claims = verifier.verify_token(token)
        if claims is None:
            logger.debug(f"Invalid JWT: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid or expired token",
                    "code": "AUTH_INVALID",
                },
                headers={"WWW-Authenticate": 'Bearer realm="boring-ui", error="invalid_token"'},
            )

        # Extract user identity
        user_id = claims.get("sub")
        if not user_id:
            logger.warning(f"JWT missing 'sub' claim: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Invalid token structure (missing 'sub')",
                    "code": "AUTH_INVALID_CLAIMS",
                },
            )

        # Extract workspace context
        workspace_id = claims.get("workspace")

        # Extract permissions (could come from 'scope', 'permissions', or custom claim)
        permissions_str = claims.get("permissions", "")
        permissions = set(p.strip() for p in permissions_str.split() if p.strip())

        # Create and inject AuthContext
        auth_context = AuthContext(
            user_id=user_id,
            workspace_id=workspace_id,
            permissions=permissions,
            claims=claims,
        )
        request.state.auth_context = auth_context

        logger.debug(f"Auth context injected: user={user_id}, workspace={workspace_id}")

        return await call_next(request)

    logger.info(f"OIDC auth middleware added (issuer: {verifier.issuer_url})")


def get_auth_context(request: Request) -> AuthContext:
    """Extract AuthContext from request state.

    Use this in route handlers to access authenticated user context.

    Args:
        request: FastAPI Request object

    Returns:
        AuthContext with user identity and permissions

    Raises:
        HTTPException: 401 if not authenticated
    """
    auth_context = getattr(request.state, "auth_context", None)
    if auth_context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return auth_context


def require_permission(permission: str) -> Callable:
    """Decorator to require a specific permission for a route.

    Usage:
        @app.get("/api/files")
        @require_permission("files:read")
        async def list_files(request: Request):
            ...

    Args:
        permission: Permission string required (e.g., "files:read")

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            auth_context = get_auth_context(request)
            if not auth_context.has_permission(permission):
                logger.warning(
                    f"Permission denied: user={auth_context.user_id}, "
                    f"required={permission}, have={auth_context.permissions}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}",
                    headers={"X-Permission-Code": f"PERM_DENIED:{permission}"},
                )
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator
