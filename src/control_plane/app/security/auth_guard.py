"""Auth guard middleware for the control plane.

Bead: bd-223o.7.3 (B3)

Extracts and verifies authentication credentials from incoming requests,
setting ``request.state.auth_identity`` on success. Protected routes
receive a 401 response when no valid credentials are present.

Auth transports (design doc section 13.1):
  - Bearer: ``Authorization: Bearer <supabase_access_token>``
  - Session cookie: read from app session (set by B2 auth callback).
    Not yet implemented — session cookie support will be added by B2.

Exempt paths (never require auth):
  - ``/auth/*`` — login/callback flows
  - ``/api/v1/app-config`` — public app branding
  - ``/health`` — health check
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .token_verify import (
    AuthIdentity,
    TokenVerificationError,
    TokenVerifier,
    extract_bearer_token,
)

# ── Constants ─────────────────────────────────────────────────────────

# Paths that never require authentication.
DEFAULT_EXEMPT_PREFIXES: tuple[str, ...] = (
    '/auth/',
    '/api/v1/app-config',
    '/health',
    '/docs',
    '/openapi.json',
)


# ── Middleware ────────────────────────────────────────────────────────


class AuthGuardMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces authentication on requests.

    For each request:
    1. If the path is exempt, pass through without auth.
    2. Attempt to extract credentials (Bearer token, then session cookie).
    3. If valid credentials found, set ``request.state.auth_identity``.
    4. If no credentials or invalid credentials on a protected path,
       return 401 with an error code.

    Args:
        app: The ASGI application.
        token_verifier: TokenVerifier instance for JWT validation.
        exempt_prefixes: Path prefixes that skip auth (defaults provided).
        require_auth: If False, auth is optional — identity is set when
            available but requests pass through without 401. Useful for
            paths that behave differently when authenticated.
    """

    def __init__(
        self,
        app,
        token_verifier: TokenVerifier,
        exempt_prefixes: tuple[str, ...] = DEFAULT_EXEMPT_PREFIXES,
        require_auth: bool = True,
    ) -> None:
        super().__init__(app)
        self._verifier = token_verifier
        self._exempt_prefixes = exempt_prefixes
        self._require_auth = require_auth

    def _is_exempt(self, path: str) -> bool:
        """Check if the path is exempt from authentication."""
        for prefix in self._exempt_prefixes:
            if path == prefix or path.startswith(prefix):
                return True
        return False

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        # Always initialize auth_identity to None.
        request.state.auth_identity = None

        # Exempt paths pass through.
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # Attempt Bearer token extraction.
        token = extract_bearer_token(request)

        # Future: attempt session cookie extraction here (B2).

        if token:
            try:
                identity = self._verifier.verify(token)
                request.state.auth_identity = identity
                return await call_next(request)
            except TokenVerificationError as exc:
                return JSONResponse(
                    status_code=401,
                    content={
                        'error': 'unauthorized',
                        'code': exc.code,
                        'detail': exc.detail,
                    },
                    headers={'WWW-Authenticate': 'Bearer'},
                )

        # No credentials found.
        if self._require_auth:
            return JSONResponse(
                status_code=401,
                content={
                    'error': 'unauthorized',
                    'code': 'no_credentials',
                    'detail': 'Authentication required',
                },
                headers={'WWW-Authenticate': 'Bearer'},
            )

        # Optional auth mode — pass through without identity.
        return await call_next(request)


# ── Dependency helper ────────────────────────────────────────────────


def get_auth_identity(request: Request) -> AuthIdentity:
    """FastAPI dependency that returns the authenticated identity.

    Use as a route dependency to enforce auth at the handler level
    (in addition to or instead of the middleware).

    Raises:
        HTTPException: 401 if no authenticated identity on the request.
    """
    from fastapi import HTTPException

    identity: AuthIdentity | None = getattr(
        request.state, 'auth_identity', None
    )
    if identity is None:
        raise HTTPException(
            status_code=401,
            detail={
                'error': 'unauthorized',
                'code': 'no_credentials',
                'detail': 'Authentication required',
            },
            headers={'WWW-Authenticate': 'Bearer'},
        )
    return identity
