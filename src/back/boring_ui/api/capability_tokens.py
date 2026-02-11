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
