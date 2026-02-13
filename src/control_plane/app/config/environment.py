"""Per-environment configuration for control-plane host, TLS, and auth URLs.

Bead: bd-223o.3 (P3)

Codifies the relationship between deployment environment, public URL,
Supabase auth callback, and security settings so they cannot fall out
of sync.

Environments:
  - ``local``: Developer workstation, HTTP, permissive CORS.
  - ``staging``: Preview/test, HTTPS via platform TLS, restricted CORS.
  - ``production``: Live, HTTPS, strict CORS, cookie Secure=True.

Configuration sources (in order):
  1. Explicit keyword arguments (tests, programmatic setup).
  2. Environment variables (Modal / Sprite runtime injection).
  3. Per-environment defaults (derived from environment type).

Key invariant:
  ``supabase_callback_url == public_url + '/auth/callback'``
  This must match the redirect URI registered in the Supabase project
  dashboard under Authentication > URL Configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

EnvironmentType = Literal['local', 'staging', 'production']

# ── Defaults per environment ────────────────────────────────────────

_LOCAL_CORS_ORIGINS = (
    'http://localhost:5173',
    'http://localhost:3000',
    'http://127.0.0.1:5173',
    'http://127.0.0.1:3000',
)

_DEFAULT_CORS_ORIGINS: dict[EnvironmentType, tuple[str, ...]] = {
    'local': _LOCAL_CORS_ORIGINS,
    'staging': (),  # Must be set from PUBLIC_URL.
    'production': (),  # Must be set from PUBLIC_URL.
}


# ── Configuration ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EnvironmentConfig:
    """Immutable per-environment configuration.

    Attributes:
        environment: Deployment environment type.
        public_url: Externally-reachable base URL (no trailing slash).
        supabase_callback_url: Full auth callback URL registered in Supabase.
        cookie_secure: Whether session cookies require HTTPS.
        cors_origins: Allowed CORS origins.
    """

    environment: EnvironmentType
    public_url: str
    supabase_callback_url: str
    cookie_secure: bool
    cors_origins: tuple[str, ...]

    @property
    def is_local(self) -> bool:
        return self.environment == 'local'

    @property
    def is_production(self) -> bool:
        return self.environment == 'production'


class EnvironmentConfigError(ValueError):
    """Raised when environment configuration is invalid."""


# ── Loading ─────────────────────────────────────────────────────────


def load_environment_config(
    *,
    environment: EnvironmentType | None = None,
    public_url: str | None = None,
    cors_origins: tuple[str, ...] | None = None,
) -> EnvironmentConfig:
    """Load environment config from env vars with optional overrides.

    Environment variables:
      - ``ENVIRONMENT``: ``local``, ``staging``, or ``production``.
      - ``PUBLIC_URL``: Externally-reachable base URL.
      - ``CORS_ORIGINS``: Comma-separated allowed origins (optional).
      - ``SUPABASE_CALLBACK_URL``: Override auto-derived callback URL.

    Args:
        environment: Override for ENVIRONMENT.
        public_url: Override for PUBLIC_URL.
        cors_origins: Override for CORS_ORIGINS.

    Returns:
        Populated EnvironmentConfig.

    Raises:
        EnvironmentConfigError: If required values are missing or invalid.
    """
    env = environment or _resolve_environment()
    url = (public_url or os.environ.get('PUBLIC_URL', '')).strip().rstrip('/')

    if not url:
        url = _default_public_url(env)

    _validate_public_url(url, env)

    callback_url = os.environ.get('SUPABASE_CALLBACK_URL', '').strip()
    if not callback_url:
        callback_url = derive_supabase_callback_url(url)

    resolved_cors = cors_origins
    if resolved_cors is None:
        cors_env = os.environ.get('CORS_ORIGINS', '').strip()
        if cors_env:
            resolved_cors = tuple(
                o.strip() for o in cors_env.split(',') if o.strip()
            )
        else:
            resolved_cors = _derive_cors_origins(env, url)

    cookie_secure = env != 'local'

    return EnvironmentConfig(
        environment=env,
        public_url=url,
        supabase_callback_url=callback_url,
        cookie_secure=cookie_secure,
        cors_origins=resolved_cors,
    )


# ── Derivation helpers ──────────────────────────────────────────────


def derive_supabase_callback_url(public_url: str) -> str:
    """Derive the Supabase auth callback URL from the public base URL.

    The result must be registered in the Supabase project dashboard
    under: Authentication > URL Configuration > Redirect URLs.

    Args:
        public_url: Externally-reachable base URL (no trailing slash).

    Returns:
        Full callback URL, e.g. ``https://boring-ui.modal.run/auth/callback``.
    """
    return f'{public_url.rstrip("/")}/auth/callback'


def validate_callback_url_consistency(
    public_url: str,
    callback_url: str,
) -> None:
    """Validate that callback URL is consistent with the public URL.

    Raises:
        EnvironmentConfigError: If the callback URL does not start with
            the public URL or does not end with ``/auth/callback``.
    """
    expected = derive_supabase_callback_url(public_url)
    if callback_url != expected:
        raise EnvironmentConfigError(
            f'Callback URL mismatch: got {callback_url!r}, '
            f'expected {expected!r} (derived from PUBLIC_URL={public_url!r}). '
            f'Ensure the Supabase dashboard redirect URL matches.'
        )


# ── Private helpers ─────────────────────────────────────────────────


def _resolve_environment() -> EnvironmentType:
    """Read ENVIRONMENT from env, default to 'local'."""
    raw = os.environ.get('ENVIRONMENT', 'local').strip().lower()
    if raw not in ('local', 'staging', 'production'):
        raise EnvironmentConfigError(
            f'Invalid ENVIRONMENT={raw!r}; '
            f'must be local, staging, or production'
        )
    return raw  # type: ignore[return-value]


def _default_public_url(env: EnvironmentType) -> str:
    """Return the default public URL for an environment."""
    if env == 'local':
        return 'http://localhost:8000'
    raise EnvironmentConfigError(
        f'PUBLIC_URL is required for environment={env!r}'
    )


def _validate_public_url(url: str, env: EnvironmentType) -> None:
    """Validate public URL scheme matches the environment."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise EnvironmentConfigError(
            f'PUBLIC_URL must include scheme and host, got {url!r}'
        )
    if env != 'local' and parsed.scheme != 'https':
        raise EnvironmentConfigError(
            f'PUBLIC_URL must use HTTPS for environment={env!r}, '
            f'got scheme={parsed.scheme!r}'
        )


def _derive_cors_origins(
    env: EnvironmentType,
    public_url: str,
) -> tuple[str, ...]:
    """Derive CORS origins from environment and public URL."""
    if env == 'local':
        return _LOCAL_CORS_ORIGINS
    # Non-local: only allow the public URL origin.
    return (public_url,)
