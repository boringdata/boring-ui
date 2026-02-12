"""SSRF and proxy hardening guardrails for sandbox mode.

When the control plane proxies requests to the workspace service,
these guardrails prevent:

  1. SSRF: Only allowlisted host:port targets are reachable.
  2. Path injection: Only allowlisted path prefixes are forwarded.
  3. Method abuse: Only allowlisted HTTP methods are proxied.
  4. Redirect following: 3xx responses are treated as errors (no auto-follow).
  5. Header leakage: Hop-by-hop and browser auth headers are stripped.
  6. Response size abuse: Strict caps on upstream response body size.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Hop-by-hop headers that must never be forwarded (RFC 2616 §13.5.1).
HOP_BY_HOP_HEADERS = frozenset({
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailer',
    'transfer-encoding',
    'upgrade',
})

# Headers from the browser that must never reach upstream.
STRIPPED_REQUEST_HEADERS = frozenset({
    'authorization',
    'cookie',
    'host',
    *HOP_BY_HOP_HEADERS,
})

# Default max response body size (10 MB).
DEFAULT_MAX_RESPONSE_BYTES = 10 * 1024 * 1024

# Allowed HTTP methods for proxy forwarding.
DEFAULT_ALLOWED_METHODS = frozenset({'GET', 'POST', 'PUT', 'DELETE', 'PATCH'})


@dataclass(frozen=True)
class AllowedTarget:
    """A single allowlisted proxy target (host:port)."""
    host: str
    port: int

    def matches(self, host: str, port: int) -> bool:
        return self.host == host and self.port == port

    def __str__(self) -> str:
        return f'{self.host}:{self.port}'


@dataclass(frozen=True)
class ProxyGuardrailConfig:
    """Configuration for proxy SSRF and hardening controls."""

    # Allowlisted target hosts. Empty = deny all.
    allowed_targets: tuple[AllowedTarget, ...] = ()

    # Allowlisted upstream path prefixes. Empty = deny all.
    allowed_path_prefixes: tuple[str, ...] = (
        '/api/',
        '/healthz',
        '/__meta/',
    )

    # Allowed HTTP methods.
    allowed_methods: frozenset[str] = DEFAULT_ALLOWED_METHODS

    # Maximum upstream response body size in bytes.
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES

    # Whether to allow following redirects (should be False for SSRF prevention).
    allow_redirects: bool = False


class ProxyRequestDenied(Exception):
    """Raised when a proxy request violates guardrail policy."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f'Proxy request denied: {reason}')


class ResponseTooLarge(Exception):
    """Raised when upstream response exceeds size cap."""

    def __init__(self, size: int, limit: int):
        self.size = size
        self.limit = limit
        super().__init__(
            f'Upstream response too large: {size} bytes (limit: {limit})'
        )


def validate_proxy_target(
    host: str,
    port: int,
    config: ProxyGuardrailConfig,
) -> None:
    """Validate that a proxy target is in the allowlist.

    Raises:
        ProxyRequestDenied: If target is not allowlisted.
    """
    if not config.allowed_targets:
        raise ProxyRequestDenied(
            'No proxy targets configured (allowed_targets is empty)'
        )
    for target in config.allowed_targets:
        if target.matches(host, port):
            return
    raise ProxyRequestDenied(
        f'Target {host}:{port} not in allowlist: '
        f'{[str(t) for t in config.allowed_targets]}'
    )


def validate_proxy_path(path: str, config: ProxyGuardrailConfig) -> None:
    """Validate that a proxy path matches an allowed prefix.

    Raises:
        ProxyRequestDenied: If path is not allowed.
    """
    if not config.allowed_path_prefixes:
        raise ProxyRequestDenied(
            'No proxy path prefixes configured (allowed_path_prefixes is empty)'
        )

    # Normalize: reject path traversal attempts
    if '..' in path:
        raise ProxyRequestDenied(f'Path traversal detected: {path!r}')

    for prefix in config.allowed_path_prefixes:
        if path.startswith(prefix) or path == prefix.rstrip('/'):
            return
    raise ProxyRequestDenied(
        f'Path {path!r} does not match any allowed prefix: '
        f'{list(config.allowed_path_prefixes)}'
    )


def validate_proxy_method(method: str, config: ProxyGuardrailConfig) -> None:
    """Validate that an HTTP method is allowed for proxying.

    Raises:
        ProxyRequestDenied: If method is not allowed.
    """
    if method.upper() not in config.allowed_methods:
        raise ProxyRequestDenied(
            f'Method {method!r} not in allowed set: '
            f'{sorted(config.allowed_methods)}'
        )


def validate_response_status(status_code: int, config: ProxyGuardrailConfig) -> None:
    """Validate that an upstream response is not a redirect (SSRF vector).

    Raises:
        ProxyRequestDenied: If response is a redirect and redirects are not allowed.
    """
    if not config.allow_redirects and 300 <= status_code < 400:
        raise ProxyRequestDenied(
            f'Upstream returned redirect ({status_code}), '
            f'redirects are disabled for SSRF prevention'
        )


def validate_response_size(
    content_length: int | None,
    config: ProxyGuardrailConfig,
) -> None:
    """Validate upstream response size before reading body.

    Raises:
        ResponseTooLarge: If Content-Length exceeds limit.
    """
    if content_length is not None and content_length > config.max_response_bytes:
        raise ResponseTooLarge(content_length, config.max_response_bytes)


def sanitize_request_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove headers that must not be forwarded upstream.

    Strips hop-by-hop headers, browser Authorization, and cookies.
    Returns a new dict with only safe headers.
    """
    return {
        k: v
        for k, v in headers.items()
        if k.lower() not in STRIPPED_REQUEST_HEADERS
    }


def sanitize_response_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove hop-by-hop headers from upstream response before forwarding to browser.

    Returns a new dict with only safe headers.
    """
    return {
        k: v
        for k, v in headers.items()
        if k.lower() not in HOP_BY_HOP_HEADERS
    }
