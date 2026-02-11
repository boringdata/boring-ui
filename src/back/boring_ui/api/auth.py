"""Authentication infrastructure: service tokens + OIDC JWT verification.

Service Token Issuance (Direct Connect):
  Issues tokens for chat services to authorize direct browser connections.
  Two token types:
    - JWT (HS256): For services that validate JWT claims (Companion/Hono)
    - Plain bearer: For services with built-in --token flag (sandbox-agent/Rust)
  Signing key lives in memory only, regenerated each boring-ui startup.

OIDC JWT Verification (Hosted Mode):
  Validates JWTs from external identity providers (Auth0, Cognito, custom IdP).
  Fetches and caches JWKS, validates signatures, extracts OIDC claims.
  Designed for hosted deployments where frontend auth is handled externally.
  See .planning/DIRECT_CONNECT_ARCHITECTURE.md and bd-1pwb.2 for design details.
"""

import os
import time
import json
import logging
from typing import Any
from datetime import datetime, timezone

import jwt  # PyJWT
import httpx

logger = logging.getLogger(__name__)


class ServiceTokenIssuer:
    """Issues JWT tokens for service authentication.

    Each boring-ui session generates a random 256-bit signing key.
    Services receive the key via env var and validate tokens independently.
    """

    def __init__(self) -> None:
        self._signing_key: bytes = os.urandom(32)

    @property
    def signing_key_hex(self) -> str:
        """Hex-encoded signing key for passing to subprocesses via env var."""
        return self._signing_key.hex()

    def issue_token(self, service: str, ttl_seconds: int = 3600) -> str:
        """Issue a standard HS256 JWT for a service.

        Args:
            service: Service name (e.g. "sandbox", "companion").
            ttl_seconds: Token lifetime in seconds (default 1 hour).

        Returns:
            Encoded JWT string.
        """
        now = int(time.time())
        payload = {
            "sub": "boring-ui",
            "svc": service,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        return jwt.encode(payload, self._signing_key, algorithm="HS256")

    def issue_query_param_token(self, service: str) -> str:
        """Short-lived token (120s) safe for SSE/WS query params.

        Mitigates log-leak risk since query params may appear in server logs.
        """
        return self.issue_token(service, ttl_seconds=120)

    def generate_service_token(self) -> str:
        """Generate a plain random bearer token for services with built-in auth.

        Used for sandbox-agent (compiled Rust binary) which accepts a fixed
        bearer token via --token CLI flag and does simple string comparison.
        Not a JWT — no claims, no expiry, valid until process restart.
        """
        return os.urandom(24).hex()

    @staticmethod
    def verify_token(
        token: str, signing_key_hex: str, expected_service: str
    ) -> dict | None:
        """Verify a JWT and return its payload, or None on failure.

        FAIL-CLOSED: returns None if signing_key_hex is empty/None.

        Args:
            token: The JWT string to verify.
            signing_key_hex: Hex-encoded signing key.
            expected_service: Expected value of the "svc" claim.

        Returns:
            Decoded payload dict on success, None on any failure.
        """
        if not signing_key_hex:
            return None  # fail-closed: no key = reject
        try:
            signing_key = bytes.fromhex(signing_key_hex)
            payload = jwt.decode(token, signing_key, algorithms=["HS256"])
            if payload.get("svc") != expected_service:
                return None
            return payload
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
            return None


class OIDCVerifier:
    """Validates JWTs from OIDC identity providers.

    Fetches and caches JWKS from the IdP's .well-known/jwks.json endpoint.
    Validates token signatures and extracts standard OIDC claims.

    Configuration via environment variables:
      OIDC_ISSUER: IdP issuer URL (e.g., https://auth.example.com)
      OIDC_AUDIENCE: Expected audience claim value
      OIDC_CACHE_TTL_SECONDS: JWKS cache lifetime (default 3600)

    Cache behavior:
      - JWKS fetched on first validation or cache expiry
      - Cache misses logged for observability (catch IdP/network issues)
      - Key rotation detected: cache refreshed on signature mismatch
    """

    def __init__(
        self,
        issuer_url: str,
        audience: str,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        """Initialize OIDC verifier.

        Args:
            issuer_url: OIDC issuer URL (e.g., https://auth.example.com)
            audience: Expected 'aud' claim value
            cache_ttl_seconds: JWKS cache lifetime in seconds
        """
        # Store original issuer URL for strict OIDC claim validation
        # Some providers (Auth0, Cognito) emit 'iss' claim WITH trailing slash,
        # so we must preserve the exact format for jwt.decode(issuer=...) matching.
        self.issuer_url = issuer_url
        self.audience = audience
        self.cache_ttl_seconds = cache_ttl_seconds

        # Normalize issuer for JWKS endpoint URL construction (strip trailing slash)
        self._issuer_url_normalized = issuer_url.rstrip("/")

        # JWKS cache: { kid -> jwk_key_object }
        self._jwks_cache: dict[str, Any] | None = None
        self._cache_expires_at: float = 0
        self._cache_hits = 0
        self._cache_misses = 0

    @property
    def cache_stats(self) -> dict[str, int]:
        """Return cache hit/miss statistics for observability."""
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "total": self._cache_hits + self._cache_misses,
        }

    def _fetch_jwks(self) -> dict[str, Any] | None:
        """Fetch JWKS from IdP's .well-known/jwks.json endpoint.

        Uses normalized issuer URL (trailing slash removed) to construct
        well-known endpoint URL.

        Returns:
            Dict of kid -> key object, or None on failure.
        """
        jwks_url = f"{self._issuer_url_normalized}/.well-known/jwks.json"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(jwks_url)
                resp.raise_for_status()
                data = resp.json()
                # Index keys by kid
                return {key.get("kid"): key for key in data.get("keys", [])}
        except Exception as e:
            logger.error(f"JWKS fetch failed from {jwks_url}: {e}")
            return None

    def _load_jwks(self) -> dict[str, Any] | None:
        """Load JWKS from cache or fetch fresh copy.

        Returns:
            Dict of kid -> key object, or None on failure.
        """
        now = time.time()

        # Cache hit: return cached JWKS
        if self._jwks_cache is not None and now < self._cache_expires_at:
            self._cache_hits += 1
            return self._jwks_cache

        # Cache miss: fetch fresh JWKS
        self._cache_misses += 1
        jwks = self._fetch_jwks()

        if jwks:
            self._jwks_cache = jwks
            self._cache_expires_at = now + self.cache_ttl_seconds
            logger.info(
                f"JWKS cache refreshed ({len(jwks)} keys, expires in {self.cache_ttl_seconds}s)"
            )

        return jwks

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """Verify a JWT from this IdP and return claims.

        Validates:
        - Token signature (using cached JWKS)
        - Issuer claim matches configured issuer_url
        - Audience claim matches configured audience
        - Token is not expired

        Key rotation is handled transparently: on signature mismatch,
        JWKS cache is refreshed and validation retried.

        Args:
            token: JWT string to verify

        Returns:
            Decoded claims dict on success, None on any failure
        """
        # Parse token without verification to get header (kid + alg)
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            alg = unverified_header.get("alg")
        except Exception as e:
            logger.debug(f"Invalid token header: {e}")
            return None

        if not kid or alg != "RS256":
            logger.debug(f"Invalid token header: kid={kid}, alg={alg} (expected RS256)")
            return None

        # Load JWKS and find the key
        jwks = self._load_jwks()
        if not jwks or kid not in jwks:
            logger.warning(f"Key {kid} not found in JWKS (cache misses: {self._cache_misses})")
            # Refresh cache in case of key rotation and retry once
            self._jwks_cache = None
            self._cache_expires_at = 0
            jwks = self._load_jwks()
            if not jwks or kid not in jwks:
                return None

        # Verify signature using the kid's key
        try:
            key_data = jwks[kid]
            # Convert JWK to PEM format for PyJWT
            key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key_data))

            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer_url,
                options={"verify_exp": True},
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidSignatureError as e:
            # Signature mismatch might indicate key rotation. Refresh JWKS and retry once.
            logger.debug(f"Invalid signature, refreshing JWKS for key rotation: {e}")
            self._jwks_cache = None
            self._cache_expires_at = 0
            jwks_retry = self._load_jwks()
            if jwks_retry and kid in jwks_retry:
                try:
                    key_retry = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwks_retry[kid]))
                    payload = jwt.decode(
                        token,
                        key_retry,
                        algorithms=["RS256"],
                        audience=self.audience,
                        issuer=self.issuer_url,
                        options={"verify_exp": True},
                    )
                    return payload
                except (jwt.InvalidTokenError, jwt.exceptions.InvalidKeyError) as retry_err:
                    # Refreshed JWKS might contain malformed/invalid key data
                    logger.debug(f"Token still invalid after JWKS refresh: {retry_err}")
                    return None
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Token validation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None

    @staticmethod
    def from_env(issuer_env: str = "OIDC_ISSUER", audience_env: str = "OIDC_AUDIENCE") -> "OIDCVerifier | None":
        """Create verifier from environment variables.

        Args:
            issuer_env: Name of env var with issuer URL
            audience_env: Name of env var with audience

        Returns:
            OIDCVerifier instance, or None if required env vars missing
        """
        issuer = os.environ.get(issuer_env)
        audience = os.environ.get(audience_env)

        if not issuer or not audience:
            logger.debug(f"OIDC not configured: missing {issuer_env} and/or {audience_env}")
            return None

        cache_ttl = int(os.environ.get("OIDC_CACHE_TTL_SECONDS", "3600"))
        return OIDCVerifier(issuer, audience, cache_ttl)
