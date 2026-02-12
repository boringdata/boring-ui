"""Internal service-to-service authentication for sandbox mode.

When WORKSPACE_MODE=sandbox, the control plane delegates requests to a
workspace service running inside a sprite. This module ensures that
the workspace API rejects requests that don't carry valid control-plane
credentials in the X-Workspace-Internal-Auth header.

Protocol (V0 - HMAC pre-shared key):
  1. Control plane and workspace service share a secret
     (WORKSPACE_INTERNAL_AUTH_SECRET env var or SandboxConfig.api_token).
  2. Control plane signs each request with HMAC-SHA256(secret, timestamp)
     and sends: X-Workspace-Internal-Auth: hmac-sha256:<timestamp>:<signature>
  3. Workspace service validates signature and rejects stale timestamps.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from .workspace_contract import INTERNAL_AUTH_HEADER

logger = logging.getLogger(__name__)

# Requests older than this are rejected (seconds).
DEFAULT_MAX_SKEW = 300  # 5 minutes


@dataclass(frozen=True)
class InternalAuthConfig:
    """Configuration for internal service auth."""
    secret: str
    max_skew_seconds: int = DEFAULT_MAX_SKEW
    enabled: bool = True


def generate_auth_token(secret: str, timestamp: float | None = None) -> str:
    """Generate an internal auth token for outbound requests.

    Args:
        secret: Shared secret between control plane and workspace service.
        timestamp: Unix timestamp. Defaults to current time.

    Returns:
        Token string in format: hmac-sha256:<timestamp>:<hex_signature>
    """
    ts = int(timestamp if timestamp is not None else time.time())
    message = str(ts).encode()
    signature = hmac.new(
        secret.encode(), message, hashlib.sha256,
    ).hexdigest()
    return f'hmac-sha256:{ts}:{signature}'


def validate_auth_token(
    token: str,
    secret: str,
    *,
    max_skew_seconds: int = DEFAULT_MAX_SKEW,
    now: float | None = None,
) -> tuple[bool, str]:
    """Validate an internal auth token.

    Args:
        token: Token from X-Workspace-Internal-Auth header.
        secret: Shared secret.
        max_skew_seconds: Maximum allowed clock skew in seconds.
        now: Current time for testing. Defaults to time.time().

    Returns:
        (valid, reason) tuple. reason is empty string on success.
    """
    if not token:
        return False, 'Missing auth token'

    parts = token.split(':')
    if len(parts) != 3:
        return False, 'Malformed token (expected hmac-sha256:timestamp:signature)'

    scheme, ts_str, provided_sig = parts

    if scheme != 'hmac-sha256':
        return False, f'Unsupported auth scheme: {scheme!r}'

    try:
        ts = int(ts_str)
    except ValueError:
        return False, 'Invalid timestamp in token'

    current_time = int(now if now is not None else time.time())
    skew = abs(current_time - ts)
    if skew > max_skew_seconds:
        return False, f'Token expired (skew={skew}s, max={max_skew_seconds}s)'

    expected_sig = hmac.new(
        secret.encode(), str(ts).encode(), hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(provided_sig, expected_sig):
        return False, 'Invalid signature'

    return True, ''


class InternalAuthMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces internal auth on proxied endpoints.

    Paths listed in `exempt_prefixes` (health/meta) skip auth checks.
    All other paths require a valid X-Workspace-Internal-Auth header.
    """

    def __init__(
        self,
        app: ASGIApp,
        auth_config: InternalAuthConfig,
        exempt_prefixes: tuple[str, ...] = ('/healthz', '/__meta/', '/health', '/docs', '/openapi.json'),
    ):
        super().__init__(app)
        self.auth_config = auth_config
        self.exempt_prefixes = exempt_prefixes

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ):
        if not self.auth_config.enabled:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.exempt_prefixes):
            return await call_next(request)

        token = request.headers.get(INTERNAL_AUTH_HEADER, '')
        valid, reason = validate_auth_token(
            token,
            self.auth_config.secret,
            max_skew_seconds=self.auth_config.max_skew_seconds,
        )

        if not valid:
            logger.warning(
                'Internal auth rejected: %s %s - %s',
                request.method, path, reason,
            )
            return JSONResponse(
                status_code=403,
                content={'detail': 'Forbidden: invalid internal credentials'},
            )

        return await call_next(request)
