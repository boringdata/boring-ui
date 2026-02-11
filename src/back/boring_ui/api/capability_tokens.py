"""Internal capability tokens for service-to-service authentication.

Implements a lightweight token system for the Hosted API -> Sandbox API trust model.
Tokens are operation-scoped, short-lived, and replay-resistant.

Architecture:
  1. Control Plane (Hosted API): Issues capability tokens for authorized operations
  2. Data Plane (Sandbox API): Validates tokens and enforces operation scoping
  3. Replay Protection: Uses JTI (JWT ID) to prevent token reuse

Token Lifecycle:
  - User requests operation (e.g., "read file /src/main.py")
  - Hosted API validates permission and workspace access
  - Hosted API issues capability token (60s TTL, operation-scoped)
  - Hosted API calls Sandbox API with token
  - Sandbox validates token signature, claims, and JTI
  - Sandbox executes operation and returns result
  - Token expires after 60 seconds (cannot be reused)
"""

import uuid
import time
import logging
from dataclasses import dataclass, field
from typing import Any
from collections import OrderedDict

import jwt

logger = logging.getLogger(__name__)


@dataclass
class CapabilityToken:
    """Represents an internal capability token.

    Tokens are operation-scoped and short-lived, designed for service-to-service
    authentication within hosted deployments.
    """

    workspace_id: str
    """Target workspace ID for the operation."""

    operations: set[str]
    """Set of allowed operations (e.g., 'files:read', 'git:status', 'exec:run')."""

    ttl_seconds: int = 60
    """Token lifetime in seconds (default 60s for operation-scoped tokens)."""

    jti: str = field(default_factory=lambda: str(uuid.uuid4()))
    """Unique token ID for replay resistance."""

    def __post_init__(self) -> None:
        """Validate token parameters."""
        if self.ttl_seconds < 5 or self.ttl_seconds > 3600:
            raise ValueError(f"TTL must be 5-3600 seconds, got {self.ttl_seconds}")
        if not self.operations:
            raise ValueError("Operations cannot be empty")
        if not all(isinstance(op, str) for op in self.operations):
            raise ValueError("All operations must be strings")

    def to_claims(self, issuer: str = "boring-ui/hosted", aud: str = "sandbox") -> dict[str, Any]:
        """Convert to JWT claims dict.

        Args:
            issuer: Token issuer identifier
            aud: Token audience (target service)

        Returns:
            Claims dict suitable for jwt.encode()
        """
        now = int(time.time())
        return {
            "iss": issuer,
            "aud": aud,
            "sub": "control-plane",
            "workspace_id": self.workspace_id,
            "ops": sorted(self.operations),  # Sort for consistent ordering
            "jti": self.jti,
            "iat": now,
            "exp": now + self.ttl_seconds,
        }


class CapabilityTokenIssuer:
    """Issues and signs capability tokens for service-to-service authentication.

    Tokens are signed with RS256 (public/private key pair) for validation
    by the Sandbox API.
    """

    def __init__(self, private_key_pem: str) -> None:
        """Initialize issuer with RSA private key.

        Args:
            private_key_pem: RSA private key in PEM format
        """
        self.private_key_pem = private_key_pem

    def issue_token(
        self,
        workspace_id: str,
        operations: set[str],
        ttl_seconds: int = 60,
    ) -> str:
        """Issue a capability token.

        Args:
            workspace_id: Target workspace
            operations: Set of allowed operations
            ttl_seconds: Token lifetime in seconds

        Returns:
            Signed JWT token string
        """
        token = CapabilityToken(
            workspace_id=workspace_id,
            operations=operations,
            ttl_seconds=ttl_seconds,
        )

        claims = token.to_claims()
        jwt_token = jwt.encode(
            claims,
            self.private_key_pem,
            algorithm="RS256",
            headers={"typ": "JWT", "kid": "capability-token"},
        )

        logger.info(
            f"Capability token issued: workspace={workspace_id}, "
            f"ops={len(operations)}, ttl={ttl_seconds}s, jti={token.jti}"
        )

        return jwt_token


class CapabilityTokenValidator:
    """Validates capability tokens (typically runs on Sandbox API).

    Verifies token signature, claims, and enforces operation scoping.
    """

    def __init__(self, public_key_pem: str) -> None:
        """Initialize validator with RSA public key.

        Args:
            public_key_pem: RSA public key in PEM format
        """
        self.public_key_pem = public_key_pem

    def validate_token(self, token: str) -> dict[str, Any] | None:
        """Validate and extract claims from token.

        Checks:
        - Token signature (RS256)
        - Issuer is control plane
        - Audience is sandbox
        - Token is not expired
        - Required claims present (workspace_id, ops, jti)

        Args:
            token: JWT token string

        Returns:
            Claims dict on success, None on any validation failure
        """
        try:
            claims = jwt.decode(
                token,
                self.public_key_pem,
                algorithms=["RS256"],
                audience="sandbox",
                issuer="boring-ui/hosted",
                options={"verify_exp": True},
            )

            # Validate required capability claims
            if "workspace_id" not in claims or "ops" not in claims or "jti" not in claims:
                logger.warning("Token missing required capability claims")
                return None

            # Validate ops is non-empty list
            ops = claims.get("ops", [])
            if not ops or not isinstance(ops, list):
                logger.warning("Token has invalid ops claim")
                return None

            return claims
        except jwt.ExpiredSignatureError:
            logger.debug("Capability token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid capability token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None

    def validate_operation(self, claims: dict[str, Any], operation: str) -> bool:
        """Check if operation is allowed by token.

        Supports wildcard matching:
        - 'files:*' - all file operations
        - '*' - all operations (dangerous, shouldn't be issued)

        Args:
            claims: Token claims dict
            operation: Operation to check (e.g., 'files:read')

        Returns:
            True if operation is allowed, False otherwise
        """
        ops = claims.get("ops", [])

        # Exact match
        if operation in ops:
            return True

        # Wildcard checks
        if "*" in ops:
            return True

        # Namespace wildcard (e.g., 'files:*' matches 'files:read')
        namespace = operation.split(":")[0] + ":*"
        if namespace in ops:
            return True

        logger.warning(f"Operation {operation} not in allowed {ops}")
        return False


class JTIReplayStore:
    """Prevents token replay attacks by tracking used JTI (JWT ID) values.

    Maintains a time-windowed cache of used JTIs with TTL matching token lifetime.
    When a token is validated, its JTI is checked against this store; if found,
    the token is rejected as a replay attempt.

    Implements automatic cleanup of expired entries to prevent unbounded memory growth.
    """

    def __init__(self, max_size: int = 10000) -> None:
        """Initialize replay store.

        Args:
            max_size: Maximum number of JTI entries to cache (default 10000)
        """
        self.max_size = max_size
        # OrderedDict for LRU eviction when max_size exceeded
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict[str, Any]:
        """Return cache statistics for observability."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": hit_rate,
            "cached_jtis": len(self._cache),
            "max_size": self.max_size,
        }

    def record_jti(self, jti: str, ttl_seconds: int) -> None:
        """Record a JTI as seen, with expiry based on token TTL.

        Args:
            jti: JWT ID value to record
            ttl_seconds: Token lifetime in seconds (use for setting expiry window)
        """
        now = time.time()
        expires_at = now + ttl_seconds

        self._cache[jti] = expires_at

        # Evict oldest entry if cache exceeds max size (LRU)
        if len(self._cache) > self.max_size:
            oldest_jti, _ = self._cache.popitem(last=False)
            logger.debug(f"JTI cache exceeded max_size, evicted oldest: {oldest_jti}")

        logger.debug(f"JTI recorded: {jti}, expires_at={expires_at}")

    def is_replayed(self, jti: str) -> bool:
        """Check if JTI has been seen before and is still within TTL.

        Automatic cleanup: expired entries are removed during check.

        Args:
            jti: JWT ID value to check

        Returns:
            True if JTI is a replay (seen and not expired), False if new
        """
        now = time.time()

        # Clean up expired entries during check (lazy cleanup)
        expired = [
            j for j, exp_at in list(self._cache.items()) if now >= exp_at
        ]
        for j in expired:
            del self._cache[j]
            logger.debug(f"JTI expired and removed from replay cache: {j}")

        # Check if JTI is in cache
        if jti in self._cache:
            self._hits += 1
            # Move to end to preserve true LRU ordering (refresh recency)
            self._cache.move_to_end(jti)
            logger.warning(f"JTI replay detected: {jti}")
            return True

        self._misses += 1
        return False
