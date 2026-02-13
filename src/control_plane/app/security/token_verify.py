"""Supabase JWT token verification using JWKS.

Bead: bd-223o.7.1 (B1)

Validates Supabase-issued access tokens by:
  1. Fetching the JWKS from the Supabase project endpoint.
  2. Caching public keys with TTL-based refresh.
  3. Verifying JWT signature (RS256), audience, and expiry.
  4. Extracting authenticated identity (user_id, email).

Auth transports (design doc section 13.1):
  - Bearer: ``Authorization: Bearer <supabase_access_token>``
  - Session cookie: handled by session middleware (B2), not here.

Configuration:
  - ``SUPABASE_URL``: Supabase project URL (e.g. ``https://xxx.supabase.co``).
  - ``SUPABASE_JWT_SECRET``: Optional fallback for HS256 (local dev only).
  - ``SUPABASE_AUDIENCE``: Expected audience claim (default: ``authenticated``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient, PyJWKClientError
from starlette.requests import Request

# ── Constants ─────────────────────────────────────────────────────────

DEFAULT_AUDIENCE = 'authenticated'
DEFAULT_ALGORITHMS = ['RS256']
JWKS_CACHE_TTL_SECONDS = 300  # 5-minute cache
BEARER_PREFIX = 'Bearer '

# ── Types ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AuthIdentity:
    """Verified identity extracted from a valid JWT.

    Attributes:
        user_id: The Supabase auth.users UUID (from ``sub`` claim).
        email: Normalized email address.
        role: Supabase role (typically ``authenticated``).
        raw_claims: Full decoded JWT payload for downstream use.
    """

    user_id: str
    email: str
    role: str = 'authenticated'
    raw_claims: dict[str, Any] = field(default_factory=dict)


class TokenVerificationError(Exception):
    """Raised when token verification fails."""

    def __init__(self, code: str, detail: str = '') -> None:
        self.code = code
        self.detail = detail
        super().__init__(f'{code}: {detail}' if detail else code)


# ── JWKS Key Provider Protocol ────────────────────────────────────────


class KeyProvider(Protocol):
    """Protocol for pluggable signing key resolution.

    Implementations fetch the signing key for a given JWT token.
    The default uses PyJWKClient with caching.
    """

    def get_signing_key(self, token: str) -> Any:
        """Return the signing key for the given unverified token."""
        ...


# ── Default JWKS Key Provider ────────────────────────────────────────


class JWKSKeyProvider:
    """Fetches signing keys from a Supabase JWKS endpoint with caching.

    The PyJWKClient handles key caching internally. We wrap it to
    provide consistent error handling and testability.

    Args:
        jwks_url: Full URL to the JWKS endpoint.
        cache_ttl: Seconds to cache fetched keys.
    """

    def __init__(
        self,
        jwks_url: str,
        cache_ttl: int = JWKS_CACHE_TTL_SECONDS,
    ) -> None:
        self._client = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=cache_ttl,
        )

    def get_signing_key(self, token: str) -> Any:
        """Fetch the signing key matching the token's ``kid`` header."""
        try:
            signing_key = self._client.get_signing_key_from_jwt(token)
            return signing_key.key
        except PyJWKClientError as exc:
            raise TokenVerificationError(
                'jwks_fetch_error',
                str(exc),
            ) from exc


# ── Static Key Provider (for HS256 / local dev) ──────────────────────


class StaticKeyProvider:
    """Uses a static secret for HS256 verification (local dev only).

    Args:
        secret: The JWT secret string.
    """

    def __init__(self, secret: str) -> None:
        self._secret = secret

    def get_signing_key(self, token: str) -> str:
        return self._secret


# ── Token Verifier ───────────────────────────────────────────────────


class TokenVerifier:
    """Verifies Supabase JWTs and extracts identity claims.

    Args:
        key_provider: A KeyProvider that resolves signing keys.
        audience: Expected ``aud`` claim value.
        algorithms: Accepted JWT algorithms.
        require_email: Whether the ``email`` claim is required.
    """

    def __init__(
        self,
        key_provider: KeyProvider,
        audience: str = DEFAULT_AUDIENCE,
        algorithms: list[str] | None = None,
        require_email: bool = True,
    ) -> None:
        self._key_provider = key_provider
        self._audience = audience
        self._algorithms = algorithms or DEFAULT_ALGORITHMS
        self._require_email = require_email

    def verify(self, token: str) -> AuthIdentity:
        """Verify a JWT and return the authenticated identity.

        Args:
            token: The raw JWT string (without ``Bearer `` prefix).

        Returns:
            AuthIdentity with verified claims.

        Raises:
            TokenVerificationError: On any verification failure.
        """
        if not token or not token.strip():
            raise TokenVerificationError('empty_token')

        # Resolve signing key.
        key = self._key_provider.get_signing_key(token)

        # Decode and verify.
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=self._algorithms,
                audience=self._audience,
                options={
                    'require': ['sub', 'exp', 'aud'],
                    'verify_exp': True,
                    'verify_aud': True,
                },
            )
        except jwt.ExpiredSignatureError:
            raise TokenVerificationError('token_expired')
        except jwt.InvalidAudienceError:
            raise TokenVerificationError(
                'invalid_audience',
                f'expected {self._audience}',
            )
        except jwt.DecodeError as exc:
            raise TokenVerificationError(
                'decode_error',
                str(exc),
            )
        except jwt.InvalidTokenError as exc:
            raise TokenVerificationError(
                'invalid_token',
                str(exc),
            )

        # Extract identity.
        user_id = claims.get('sub')
        if not user_id:
            raise TokenVerificationError('missing_sub_claim')

        email = claims.get('email', '')
        if self._require_email and not email:
            raise TokenVerificationError('missing_email_claim')

        role = claims.get('role', 'authenticated')

        return AuthIdentity(
            user_id=user_id,
            email=email.lower() if email else '',
            role=role,
            raw_claims=claims,
        )


# ── Request helpers ──────────────────────────────────────────────────


def extract_bearer_token(request: Request) -> str | None:
    """Extract a Bearer token from the Authorization header.

    Returns None if no Authorization header or non-Bearer scheme.
    """
    auth_header = request.headers.get('authorization', '')
    if auth_header.startswith(BEARER_PREFIX):
        return auth_header[len(BEARER_PREFIX):].strip()
    return None


# ── Factory ──────────────────────────────────────────────────────────


def create_token_verifier(
    supabase_url: str | None = None,
    jwt_secret: str | None = None,
    audience: str = DEFAULT_AUDIENCE,
) -> TokenVerifier:
    """Create a TokenVerifier with appropriate key provider.

    Prefers JWKS (RS256) when ``supabase_url`` is provided.
    Falls back to static secret (HS256) when only ``jwt_secret`` given.

    Args:
        supabase_url: Supabase project URL for JWKS discovery.
        jwt_secret: Fallback JWT secret for HS256 (local dev).
        audience: Expected audience claim.

    Returns:
        Configured TokenVerifier.

    Raises:
        ValueError: If neither URL nor secret is provided.
    """
    if supabase_url:
        jwks_url = f'{supabase_url.rstrip("/")}/auth/v1/.well-known/jwks.json'
        provider = JWKSKeyProvider(jwks_url)
        return TokenVerifier(
            key_provider=provider,
            audience=audience,
            algorithms=['RS256'],
        )

    if jwt_secret:
        provider = StaticKeyProvider(jwt_secret)
        return TokenVerifier(
            key_provider=provider,
            audience=audience,
            algorithms=['HS256'],
        )

    raise ValueError(
        'Either supabase_url (for JWKS) or jwt_secret (for HS256) is required'
    )
