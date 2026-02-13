"""CSRF protection for the control plane.

Bead: bd-3499 (B6)

Implements Synchronizer Token pattern:
  - Server generates a per-session CSRF token on login/session init.
  - Frontend includes the token as ``X-CSRF-Token`` header on mutations.
  - Middleware validates the header on POST/PUT/PATCH/DELETE requests.
  - Timing-safe comparison prevents timing side-channels.

Design decisions:
  - Token is 32 bytes of ``secrets.token_urlsafe`` (256-bit entropy).
  - Validation uses ``hmac.compare_digest`` for constant-time comparison.
  - Safe methods (GET, HEAD, OPTIONS) are always exempt.
  - API paths that are explicitly exempt (e.g. auth callbacks) can be
    configured via ``exempt_paths``.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# ── Constants ─────────────────────────────────────────────────────────

CSRF_TOKEN_HEADER = 'X-CSRF-Token'
CSRF_TOKEN_BYTES = 32  # 256-bit entropy
SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})

# ── Token generation & validation ─────────────────────────────────────


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token.

    Returns a URL-safe base64-encoded token with 256 bits of entropy.
    """
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


class CSRFError(Exception):
    """Raised when CSRF validation fails."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def validate_csrf_token(
    expected: str | None,
    actual: str | None,
) -> None:
    """Validate a CSRF token using timing-safe comparison.

    Args:
        expected: The token stored in the server session.
        actual: The token submitted by the client.

    Raises:
        CSRFError: If validation fails (missing or mismatched tokens).
    """
    if expected is None:
        raise CSRFError('no_session_token')

    if actual is None:
        raise CSRFError('missing_csrf_token')

    if not actual:
        raise CSRFError('empty_csrf_token')

    if not hmac.compare_digest(expected, actual):
        raise CSRFError('csrf_token_mismatch')


# ── Middleware ────────────────────────────────────────────────────────


class CSRFMiddleware(BaseHTTPMiddleware):
    """Starlette middleware enforcing CSRF token validation.

    For mutation requests (POST/PUT/PATCH/DELETE), the middleware checks
    that the ``X-CSRF-Token`` header matches the session's CSRF token.

    The session token is read from ``request.state.csrf_token``, which
    must be set by the upstream auth/session middleware before this
    middleware runs.

    Args:
        app: The ASGI application.
        exempt_paths: Path prefixes that skip CSRF validation
            (e.g. ``['/auth/']`` for OAuth callbacks).
        exempt_check: Optional callable ``(request) -> bool`` for
            custom exemption logic (e.g. service-to-service calls
            authenticated by bearer token).
    """

    def __init__(
        self,
        app,
        exempt_paths: tuple[str, ...] = (),
        exempt_check: Callable[[Request], bool] | None = None,
    ) -> None:
        super().__init__(app)
        self._exempt_paths = exempt_paths
        self._exempt_check = exempt_check

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        # Safe methods never need CSRF protection.
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Check path exemptions.
        path = request.url.path
        for prefix in self._exempt_paths:
            if path.startswith(prefix):
                return await call_next(request)

        # Check custom exemption (e.g. bearer-token-authenticated APIs).
        if self._exempt_check is not None and self._exempt_check(request):
            return await call_next(request)

        # Validate the CSRF token.
        session_token: str | None = getattr(
            request.state, 'csrf_token', None
        )
        header_token: str | None = request.headers.get(CSRF_TOKEN_HEADER)

        try:
            validate_csrf_token(session_token, header_token)
        except CSRFError as exc:
            return JSONResponse(
                status_code=403,
                content={
                    'error': 'csrf_validation_failed',
                    'reason': exc.reason,
                },
            )

        return await call_next(request)
