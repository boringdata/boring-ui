"""Modal secret configuration and validation for control-plane auth.

Bead: bd-223o.2 (P2)

Codifies the required Modal secrets for control-plane and runtime
authentication. Validates that all expected environment variables are
present at startup and provides a unified configuration surface.

Required Modal secrets:
    - ``sprite-bearer``: SPRITE_BEARER_TOKEN for workspace proxy auth.
    - ``supabase-creds``: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY,
      SUPABASE_SERVICE_ROLE_KEY for auth backend.
    - ``jwt-secret``: SUPABASE_JWT_SECRET for HS256 fallback (local dev).
    - ``anthropic-key``: ANTHROPIC_API_KEY for Claude completions.
    - ``session-config``: SESSION_SECRET for session JWT signing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence


# ── Secret definitions ─────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ModalSecretSpec:
    """Specification for a required Modal secret.

    Attributes:
        name: Modal secret name (``modal.Secret.from_name(name)``).
        required_keys: Environment variable names this secret must provide.
        description: Human-readable purpose.
        optional: If True, missing secret is a warning not an error.
    """

    name: str
    required_keys: tuple[str, ...]
    description: str
    optional: bool = False


CONTROL_PLANE_SECRETS: tuple[ModalSecretSpec, ...] = (
    ModalSecretSpec(
        name='sprite-bearer',
        required_keys=('SPRITE_BEARER_TOKEN',),
        description='Server-side bearer token for workspace proxy auth',
    ),
    ModalSecretSpec(
        name='supabase-creds',
        required_keys=('SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'SUPABASE_SERVICE_ROLE_KEY'),
        description='Supabase project credentials for auth backend',
    ),
    ModalSecretSpec(
        name='jwt-secret',
        required_keys=('SUPABASE_JWT_SECRET',),
        description='JWT signing secret for HS256 local-dev fallback',
        optional=True,
    ),
    ModalSecretSpec(
        name='anthropic-key',
        required_keys=('ANTHROPIC_API_KEY',),
        description='Anthropic API key for Claude completions',
    ),
    ModalSecretSpec(
        name='session-config',
        required_keys=('SESSION_SECRET',),
        description='Session JWT signing secret for control-plane cookies',
    ),
)

# Keys that must never appear in logs, responses, or error payloads.
SECRET_KEYS: frozenset[str] = frozenset({
    'SPRITE_BEARER_TOKEN',
    'SUPABASE_SERVICE_ROLE_KEY',
    'SUPABASE_JWT_SECRET',
    'ANTHROPIC_API_KEY',
    'SESSION_SECRET',
})


# ── Validation ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SecretValidationResult:
    """Result of validating Modal secret environment variables.

    Attributes:
        present: Keys found in the environment.
        missing: Required keys not found.
        warnings: Optional keys not found (non-fatal).
    """

    present: tuple[str, ...]
    missing: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True if no required keys are missing."""
        return len(self.missing) == 0


def validate_secret_environment(
    specs: Sequence[ModalSecretSpec] = CONTROL_PLANE_SECRETS,
) -> SecretValidationResult:
    """Check that all required secret environment variables are set.

    Reads from ``os.environ`` (which is populated by Modal secret
    injection at runtime).

    Args:
        specs: Secret specifications to validate against.

    Returns:
        SecretValidationResult with present, missing, and warning keys.
    """
    present: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []

    for spec in specs:
        for key in spec.required_keys:
            value = os.environ.get(key, '').strip()
            if value:
                present.append(key)
            elif spec.optional:
                warnings.append(key)
            else:
                missing.append(key)

    return SecretValidationResult(
        present=tuple(present),
        missing=tuple(missing),
        warnings=tuple(warnings),
    )


def check_no_secret_leakage(text: str) -> list[str]:
    """Check that a text blob does not contain known secret values.

    Scans ``text`` for the actual runtime values of any keys in
    ``SECRET_KEYS``. Returns the names of any leaked secrets.

    This is a defense-in-depth check — the proxy security layer
    already strips sensitive headers from responses.

    Args:
        text: String to scan (e.g., log line, response body).

    Returns:
        List of secret key names whose values appear in the text.
    """
    leaked: list[str] = []
    for key in SECRET_KEYS:
        value = os.environ.get(key, '')
        if value and value in text:
            leaked.append(key)
    return leaked
