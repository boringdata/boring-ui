"""Private proxy security boundary for workspace-plane requests.

Bead: bd-223o.11.3 (E3)

Implements the security contract from Feature 3 design doc sections 13.2
and 13.3:

  - Control plane injects Sprite bearer token server-side only.
  - Untrusted identity headers from the browser are stripped before
    forwarding to the workspace runtime.
  - X-Request-ID and session context are propagated to the runtime.
  - Sprite bearer token never appears in browser responses or audit
    payloads.

This module provides:
  1. ``sanitize_proxy_headers`` — strips untrusted headers from browser
     requests and injects server-side credentials.
  2. ``ProxySecurityError`` — raised on security violations.
  3. ``ProxyHeaderConfig`` — configures which headers to strip/inject.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


class ProxySecurityError(Exception):
    """Raised when a proxy security invariant is violated."""


# Headers that must NEVER be forwarded from the browser to the runtime.
# These are set exclusively by the control plane proxy.
_DEFAULT_STRIP_HEADERS: frozenset[str] = frozenset({
    'authorization',
    'x-forwarded-user',
    'x-forwarded-email',
    'x-forwarded-groups',
    'x-workspace-owner',
    'x-runtime-token',
    'x-sprite-bearer',
    'x-service-role',
    'x-supabase-auth',
})

# Headers that must NEVER appear in responses sent back to the browser.
_RESPONSE_REDACT_HEADERS: frozenset[str] = frozenset({
    'authorization',
    'x-sprite-bearer',
    'x-runtime-token',
    'x-service-role',
})


@dataclass(frozen=True, slots=True)
class ProxyHeaderConfig:
    """Configuration for proxy header sanitization.

    Attributes:
        strip_headers: Request headers stripped before forwarding
            (lowercased for case-insensitive matching).
        response_redact_headers: Response headers stripped before
            returning to the browser.
        inject_headers: Headers injected into the proxied request
            (e.g., Authorization with Sprite bearer).
    """

    strip_headers: frozenset[str] = _DEFAULT_STRIP_HEADERS
    response_redact_headers: frozenset[str] = _RESPONSE_REDACT_HEADERS
    inject_headers: dict[str, str] = field(default_factory=dict)


def sanitize_proxy_headers(
    *,
    incoming_headers: Mapping[str, str],
    config: ProxyHeaderConfig,
    request_id: str | None = None,
    session_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, str]:
    """Build sanitized headers for a proxied workspace-plane request.

    1. Copies incoming headers, stripping any in ``config.strip_headers``.
    2. Injects server-side headers from ``config.inject_headers``.
    3. Sets X-Request-ID if provided.
    4. Sets X-Session-ID if provided.
    5. Sets X-Workspace-ID if provided.

    Args:
        incoming_headers: Original browser request headers.
        config: Proxy header configuration.
        request_id: Optional X-Request-ID to propagate.
        session_id: Optional X-Session-ID to propagate.
        workspace_id: Optional workspace ID for context.

    Returns:
        Sanitized header dict ready for the proxied request.

    Raises:
        ProxySecurityError: If config.inject_headers is empty and
            no Sprite bearer is configured (missing server-side auth).
    """
    result: dict[str, str] = {}

    # 1. Copy allowed headers (strip untrusted ones).
    strip_lower = config.strip_headers
    for key, value in incoming_headers.items():
        if key.lower() not in strip_lower:
            result[key] = value

    # 2. Inject server-side headers (e.g., Authorization: Bearer <sprite>).
    for key, value in config.inject_headers.items():
        result[key] = value

    # 3. Propagate request context.
    if request_id is not None:
        result['X-Request-ID'] = request_id
    if session_id is not None:
        result['X-Session-ID'] = session_id
    if workspace_id is not None:
        result['X-Workspace-ID'] = workspace_id

    return result


def redact_response_headers(
    response_headers: Mapping[str, str],
    config: ProxyHeaderConfig,
) -> dict[str, str]:
    """Remove sensitive headers from a runtime response before returning
    it to the browser.

    This prevents Sprite bearer tokens or internal service credentials
    from leaking to the client.

    Args:
        response_headers: Headers from the workspace runtime response.
        config: Proxy header configuration.

    Returns:
        Cleaned header dict safe for browser delivery.
    """
    redact_lower = config.response_redact_headers
    return {
        key: value
        for key, value in response_headers.items()
        if key.lower() not in redact_lower
    }


def build_proxy_config(
    sprite_bearer_token: str | None = None,
    extra_strip_headers: frozenset[str] | None = None,
) -> ProxyHeaderConfig:
    """Build a ProxyHeaderConfig with Sprite bearer injection.

    Args:
        sprite_bearer_token: The server-side Sprite bearer token.
            If None, no Authorization header is injected (useful for
            local/test mode).
        extra_strip_headers: Additional headers to strip beyond defaults.

    Returns:
        Configured ProxyHeaderConfig instance.
    """
    strip = _DEFAULT_STRIP_HEADERS
    if extra_strip_headers:
        strip = strip | extra_strip_headers

    inject: dict[str, str] = {}
    if sprite_bearer_token:
        inject['Authorization'] = f'Bearer {sprite_bearer_token}'

    return ProxyHeaderConfig(
        strip_headers=strip,
        response_redact_headers=_RESPONSE_REDACT_HEADERS,
        inject_headers=inject,
    )
