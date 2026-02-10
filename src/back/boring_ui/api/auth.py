"""Service token issuance for Direct Connect architecture.

Issues tokens for chat services to authorize direct browser connections.
Two token types:
  - JWT (HS256): For services that validate JWT claims (Companion/Hono)
  - Plain bearer: For services with built-in --token flag (sandbox-agent/Rust)

Signing key lives in memory only, regenerated each boring-ui startup.
See .planning/DIRECT_CONNECT_ARCHITECTURE.md for design details.
"""

import os
import time

import jwt  # PyJWT


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
