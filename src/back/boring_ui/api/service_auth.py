"""Service-to-service authentication and key rotation for hosted deployments.

Implements mutual authentication between Hosted API (control plane) and Sandbox API
(data plane) using signed service tokens. Supports key rotation with configurable
grace periods.

Architecture:
  1. Hosted API signs requests using private key (signs service identity)
  2. Sandbox API validates signatures using public key (verifies caller identity)
  3. Key rotation: maintain multiple keys during transition window
  4. Fail-closed: unsigned or invalid requests always rejected
"""

import os
import time
import json
import logging
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

import jwt

logger = logging.getLogger(__name__)


@dataclass
class ServiceIdentity:
    """Service identity claims for service-to-service authentication."""

    service_name: str
    """Name of calling service (e.g., 'hosted-api', 'control-plane')."""

    issued_at: int
    """Token issuance timestamp (iat claim)."""

    expires_at: int
    """Token expiration timestamp (exp claim)."""

    key_version: int
    """Key version used for signing (enables rotation tracking)."""

    def to_claims(self) -> dict[str, Any]:
        """Convert to JWT claims dict."""
        return {
            "iss": "boring-ui",
            "sub": self.service_name,
            "iat": self.issued_at,
            "exp": self.expires_at,
            "key_version": self.key_version,
        }


class ServiceTokenSigner:
    """Signs service authentication tokens for control plane → sandbox calls.

    Maintains a single active key version. Key rotation is managed by
    updating the key material and incrementing the version.
    """

    def __init__(self, private_key_pem: str, service_name: str = "hosted-api") -> None:
        """Initialize signer with RSA private key.

        Args:
            private_key_pem: RSA private key in PEM format
            service_name: Name of this service (default: hosted-api)
        """
        self.private_key_pem = private_key_pem
        self.service_name = service_name
        self._current_version = 1

    @property
    def current_key_version(self) -> int:
        """Get current key version."""
        return self._current_version

    def sign_request(self, ttl_seconds: int = 60) -> str:
        """Sign a service request and return JWT token.

        Args:
            ttl_seconds: Token lifetime in seconds

        Returns:
            Signed JWT token string
        """
        now = int(time.time())
        identity = ServiceIdentity(
            service_name=self.service_name,
            issued_at=now,
            expires_at=now + ttl_seconds,
            key_version=self._current_version,
        )

        claims = identity.to_claims()
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
        """Rotate to a new key version.

        Args:
            new_private_key_pem: New RSA private key in PEM format

        Returns:
            New key version number
        """
        self.private_key_pem = new_private_key_pem
        self._current_version += 1

        logger.info(
            f"Service key rotated: service={self.service_name}, "
            f"new_version={self._current_version}"
        )

        return self._current_version


class ServiceTokenValidator:
    """Validates service authentication tokens on sandbox API.

    Supports key rotation: maintains multiple key versions during transition
    window. Old keys are accepted during grace period, then retired.

    Configuration:
      SERVICE_KEY_VERSIONS: JSON dict mapping version -> public key PEM
                           Example: '{"1": "-----BEGIN PUBLIC KEY-----...", "2": "..."}'
      SERVICE_KEY_ROTATION_GRACE_SECONDS: Grace period for old keys (default 300s)
    """

    def __init__(
        self,
        key_versions: dict[int, str],
        current_version: int = 1,
        grace_period_seconds: int = 300,
    ) -> None:
        """Initialize validator with key versions.

        Args:
            key_versions: Dict mapping key version -> public key PEM
            current_version: Current active key version
            grace_period_seconds: Seconds to accept old keys after rotation
        """
        self.key_versions = key_versions
        self.current_version = current_version
        self.grace_period_seconds = grace_period_seconds
        # Track when keys were retired for grace period enforcement
        self._key_retirement_times: dict[int, float] = {}
        self._validation_attempts = 0
        self._validation_successes = 0
        self._rejected_old_keys = 0

    @property
    def stats(self) -> dict[str, Any]:
        """Return validation statistics for observability."""
        total = self._validation_attempts
        success_rate = (
            self._validation_successes / total if total > 0 else 0.0
        )
        return {
            "attempts": self._validation_attempts,
            "successes": self._validation_successes,
            "success_rate": success_rate,
            "rejected_old_keys": self._rejected_old_keys,
            "available_versions": sorted(self.key_versions.keys()),
            "current_version": self.current_version,
        }

    def validate_token(self, token: str, accepted_services: list[str] | None = None) -> dict[str, Any] | None:
        """Validate service authentication token.

        Checks:
        - Token signature (RS256)
        - Key version is available (current or within grace period)
        - Token not expired
        - Service name is in accepted list (if provided)

        Args:
            token: JWT token string
            accepted_services: List of service names to accept
                              (None = accept all services)

        Returns:
            Claims dict on success, None on any validation failure
        """
        self._validation_attempts += 1

        try:
            # Parse unverified header to get key version
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid", "")
            key_version_str = kid.replace("service-v", "")

            try:
                key_version = int(key_version_str)
            except ValueError:
                logger.debug(f"Invalid key version format in kid: {kid}")
                return None

            # Get public key for this version
            if key_version not in self.key_versions:
                logger.warning(f"Token signed with unknown key version: {key_version}")
                return None

            # Check if key version is still valid (current or within grace period)
            is_current = key_version == self.current_version
            is_retired = key_version in self._key_retirement_times
            is_grace_period = False

            if key_version < self.current_version:
                # Old key: check if within grace period
                if not is_retired:
                    # Never retired: accept (not yet past grace period)
                    is_grace_period = True
                else:
                    # Was retired: check grace period elapsed
                    retired_at = self._key_retirement_times[key_version]
                    grace_expiry = retired_at + self.grace_period_seconds
                    if time.time() < grace_expiry:
                        is_grace_period = True
                    else:
                        logger.warning(
                            f"Token from key version past grace period: {key_version} "
                            f"(retired at {retired_at}, grace expired at {grace_expiry})"
                        )
                        return None
            elif key_version > self.current_version:
                # Future key: always reject
                logger.warning(
                    f"Token signed with future key version: {key_version} "
                    f"(current: {self.current_version})"
                )
                return None

            if not is_current and not is_grace_period:
                return None

            # Decode and verify token
            public_key = self.key_versions[key_version]
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer="boring-ui",
                options={"verify_exp": True},
            )

            # Validate service name (distinguish between None and empty list)
            service_name = claims.get("sub", "")
            if accepted_services is not None:  # Explicit allowlist provided
                if service_name not in accepted_services:
                    logger.warning(
                        f"Token from unauthorized service: {service_name} "
                        f"(accepted: {accepted_services})"
                    )
                    return None

            # Track if old key was used during grace period
            if is_grace_period:
                self._rejected_old_keys += 1
                logger.info(
                    f"Token from old key version accepted during grace period: "
                    f"version={key_version}, service={service_name}"
                )

            self._validation_successes += 1
            return claims

        except jwt.ExpiredSignatureError:
            logger.debug("Service token expired")
            return None
        except jwt.InvalidSignatureError:
            logger.warning(f"Service token signature invalid for version {key_version}")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Service token validation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Service token validation error: {e}")
            return None

    def add_key_version(self, key_version: int, public_key_pem: str) -> None:
        """Add a new key version (during rotation).

        Args:
            key_version: Key version number
            public_key_pem: Public key in PEM format
        """
        self.key_versions[key_version] = public_key_pem
        if key_version > self.current_version:
            self.current_version = key_version
        logger.info(f"Added key version {key_version}, current version now {self.current_version}")

    def retire_key_version(self, key_version: int) -> bool:
        """Retire an old key version.

        Records retirement time for grace period enforcement.
        Key is kept in key_versions for validation during grace period.

        Args:
            key_version: Key version to retire

        Returns:
            True if retired, False if version doesn't exist
        """
        if key_version not in self.key_versions:
            return False

        # Record retirement time for grace period enforcement
        # Keep key available for validation during grace period
        self._key_retirement_times[key_version] = time.time()
        logger.info(f"Retired key version {key_version}, grace period active for {self.grace_period_seconds}s")
        return True

    @staticmethod
    def from_env(
        versions_env: str = "SERVICE_KEY_VERSIONS",
        current_version_env: str = "SERVICE_CURRENT_VERSION",
        grace_period_env: str = "SERVICE_KEY_ROTATION_GRACE_SECONDS",
    ) -> "ServiceTokenValidator | None":
        """Create validator from environment variables.

        Expected format for SERVICE_KEY_VERSIONS:
            '{"1": "-----BEGIN PUBLIC KEY-----...-----END PUBLIC KEY-----", ...}'

        Args:
            versions_env: Name of env var with key versions JSON
            current_version_env: Name of env var with current version
            grace_period_env: Name of env var with grace period

        Returns:
            ServiceTokenValidator instance, or None if env vars missing or malformed
        """
        versions_json = os.environ.get(versions_env)
        if not versions_json:
            logger.debug(f"Service auth not configured: missing {versions_env}")
            return None

        try:
            key_versions_dict = json.loads(versions_json)
            # Convert string keys to int
            key_versions = {int(k): v for k, v in key_versions_dict.items()}
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse {versions_env}: {e}")
            return None

        # Parse numeric env vars with error handling
        try:
            current_version = int(os.environ.get(current_version_env, "1"))
        except ValueError as e:
            logger.error(f"Failed to parse {current_version_env}: {e}")
            return None

        try:
            grace_period = int(os.environ.get(grace_period_env, "300"))
        except ValueError as e:
            logger.error(f"Failed to parse {grace_period_env}: {e}")
            return None

        return ServiceTokenValidator(key_versions, current_version, grace_period)
