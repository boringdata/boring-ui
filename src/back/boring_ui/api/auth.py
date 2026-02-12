"""Authentication infrastructure: token issuance/signing + OIDC JWT verification.

ServiceTokenIssuer (Direct Connect):
  HS256 JWTs for browser→subprocess service auth (Companion, sandbox-agent).
  Signing key lives in memory only, regenerated each boring-ui startup.

ServiceTokenSigner (Hosted Mode, service-to-service):
  RS256 JWTs for control plane → sandbox data plane trust.
  Used by hosted mode to sign requests to the sandbox API.

OIDCVerifier (Hosted Mode, user auth):
  Validates JWTs from external identity providers (Auth0, Cognito, custom IdP).
  Fetches and caches JWKS, validates signatures, extracts OIDC claims.
"""

import os
import time
import json
import logging
from typing import Any

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


class ServiceTokenSigner:
    """Signs RS256 service tokens for control plane → sandbox calls.

    Used in hosted mode for service-to-service authentication. Maintains a
    single active key version. Key rotation is managed by updating the key
    material and incrementing the version.
    """

    def __init__(self, private_key_pem: str, service_name: str = "hosted-api") -> None:
        self.private_key_pem = private_key_pem
        self.service_name = service_name
        self._current_version = 1

    @property
    def current_key_version(self) -> int:
        return self._current_version

    def sign_request(self, ttl_seconds: int = 60) -> str:
        """Sign a service request and return JWT token."""
        now = int(time.time())
        claims = {
            "iss": "boring-ui",
            "sub": self.service_name,
            "iat": now,
            "exp": now + ttl_seconds,
            "key_version": self._current_version,
        }
        token = jwt.encode(
            claims,
            self.private_key_pem,
            algorithm="RS256",
            headers={
                "typ": "JWT",
                "kid": f"service-v{self._current_version}",
                "service": self.service_name,
            },
        )
        logger.debug(
            f"Service token signed: service={self.service_name}, "
            f"key_version={self._current_version}, ttl={ttl_seconds}s"
        )
        return token

    def rotate_key(self, new_private_key_pem: str) -> int:
        """Rotate to a new key version. Returns new version number."""
        self.private_key_pem = new_private_key_pem
        self._current_version += 1
        logger.info(
            f"Service key rotated: service={self.service_name}, "
            f"new_version={self._current_version}"
        )
        return self._current_version


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
