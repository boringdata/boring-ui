"""Control-plane secret configuration and validation.

Bead: bd-223o.2 (P2)

Loads, validates, and provides typed access to all secrets required by the
control plane: Supabase/JWKS credentials, session signing key, and Sprite
bearer token.

Secret sources (in order of precedence):
  1. Environment variables (Modal injects secrets as env vars).
  2. Explicit keyword arguments (for testing and local dev).

Security invariants:
  - Secrets are never included in ``str()`` or ``repr()`` output.
  - ``ControlPlaneSecrets`` is immutable (frozen dataclass).
  - Validation fails fast on missing required secrets at startup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class SecretValidationError(ValueError):
    """Raised when required secrets are missing or invalid."""

    def __init__(self, missing: list[str], invalid: list[str] | None = None) -> None:
        self.missing = missing
        self.invalid = invalid or []
        parts = []
        if missing:
            parts.append(f'missing: {", ".join(missing)}')
        if self.invalid:
            parts.append(f'invalid: {", ".join(self.invalid)}')
        super().__init__(f'Secret validation failed — {"; ".join(parts)}')


# ── Minimum lengths for security ────────────────────────────────────

_MIN_SESSION_SECRET_LENGTH = 32
_MIN_SPRITE_BEARER_LENGTH = 32


# ── Secret container ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ControlPlaneSecrets:
    """Immutable typed container for all control-plane secrets.

    Attributes:
        supabase_url: Supabase project URL for JWKS discovery.
        supabase_jwt_secret: Optional fallback for HS256 (local dev).
        session_secret: Secret key for signing session cookies (HS256).
        sprite_bearer_token: Bearer token for authenticating proxy
            requests to workspace runtimes (optional in local mode).
    """

    supabase_url: str
    supabase_jwt_secret: str
    session_secret: str
    sprite_bearer_token: str

    def __repr__(self) -> str:
        return (
            'ControlPlaneSecrets('
            f'supabase_url={self.supabase_url!r}, '
            'supabase_jwt_secret=<redacted>, '
            'session_secret=<redacted>, '
            'sprite_bearer_token=<redacted>)'
        )

    def __str__(self) -> str:
        return self.__repr__()


# ── Loading ─────────────────────────────────────────────────────────


def load_control_plane_secrets(
    *,
    supabase_url: str | None = None,
    supabase_jwt_secret: str | None = None,
    session_secret: str | None = None,
    sprite_bearer_token: str | None = None,
    require_sprite_bearer: bool = False,
) -> ControlPlaneSecrets:
    """Load secrets from environment with optional explicit overrides.

    Environment variables (Modal secret names in parentheses):
      - ``SUPABASE_URL``           (supabase-auth)
      - ``SUPABASE_JWT_SECRET``    (supabase-auth)
      - ``SESSION_SECRET``         (session-config)
      - ``SPRITE_BEARER_TOKEN``    (sprite-bearer)

    Args:
        supabase_url: Override for SUPABASE_URL.
        supabase_jwt_secret: Override for SUPABASE_JWT_SECRET.
        session_secret: Override for SESSION_SECRET.
        sprite_bearer_token: Override for SPRITE_BEARER_TOKEN.
        require_sprite_bearer: If True, SPRITE_BEARER_TOKEN is required.

    Returns:
        Populated ControlPlaneSecrets instance.

    Raises:
        SecretValidationError: If required secrets are missing or invalid.
    """
    resolved_supabase_url = (
        supabase_url or os.environ.get('SUPABASE_URL', '')
    ).strip()
    resolved_jwt_secret = (
        supabase_jwt_secret or os.environ.get('SUPABASE_JWT_SECRET', '')
    ).strip()
    resolved_session_secret = (
        session_secret or os.environ.get('SESSION_SECRET', '')
    ).strip()
    resolved_sprite_bearer = (
        sprite_bearer_token or os.environ.get('SPRITE_BEARER_TOKEN', '')
    ).strip()

    secrets = ControlPlaneSecrets(
        supabase_url=resolved_supabase_url,
        supabase_jwt_secret=resolved_jwt_secret,
        session_secret=resolved_session_secret,
        sprite_bearer_token=resolved_sprite_bearer,
    )

    validate_secrets(secrets, require_sprite_bearer=require_sprite_bearer)
    return secrets


# ── Validation ──────────────────────────────────────────────────────


def validate_secrets(
    secrets: ControlPlaneSecrets,
    *,
    require_sprite_bearer: bool = False,
) -> None:
    """Validate that all required secrets are present and well-formed.

    Required:
      - ``supabase_url`` — must be non-empty (JWKS or HS256 fallback needs it,
        unless ``supabase_jwt_secret`` is provided for HS256).
      - ``session_secret`` — must be >= 32 characters.

    Conditionally required:
      - ``sprite_bearer_token`` — required when ``require_sprite_bearer=True``
        (hosted mode); must be >= 32 characters.

    At least one of ``supabase_url`` or ``supabase_jwt_secret`` must be set.

    Raises:
        SecretValidationError: On validation failure.
    """
    missing: list[str] = []
    invalid: list[str] = []

    # At least one Supabase credential is required.
    if not secrets.supabase_url and not secrets.supabase_jwt_secret:
        missing.append('SUPABASE_URL or SUPABASE_JWT_SECRET')

    # Session secret is always required.
    if not secrets.session_secret:
        missing.append('SESSION_SECRET')
    elif len(secrets.session_secret) < _MIN_SESSION_SECRET_LENGTH:
        invalid.append(
            f'SESSION_SECRET (min {_MIN_SESSION_SECRET_LENGTH} chars, '
            f'got {len(secrets.session_secret)})'
        )

    # Sprite bearer is conditionally required.
    if require_sprite_bearer:
        if not secrets.sprite_bearer_token:
            missing.append('SPRITE_BEARER_TOKEN')
        elif len(secrets.sprite_bearer_token) < _MIN_SPRITE_BEARER_LENGTH:
            invalid.append(
                f'SPRITE_BEARER_TOKEN (min {_MIN_SPRITE_BEARER_LENGTH} chars, '
                f'got {len(secrets.sprite_bearer_token)})'
            )

    if missing or invalid:
        raise SecretValidationError(missing=missing, invalid=invalid)
