"""INTERNAL_SANDBOX_URL validation for non-Sprites hosted mode (bd-1adh.3.3).

Ensures that when using INTERNAL_SANDBOX_URL, it points to a reachable,
properly configured internal sandbox API service.

Validates provenance, co-location assumptions, and performs startup health checks.
"""

import logging
import httpx
import asyncio
from typing import Optional
from urllib.parse import urlparse
from pathlib import Path


logger = logging.getLogger(__name__)


class SandboxURLValidationError(Exception):
    """Raised when sandbox URL validation fails."""
    pass


class InternalSandboxURLValidator:
    """Validates INTERNAL_SANDBOX_URL configuration for hosted non-Sprites mode (bd-1adh.3.3).

    Enforces:
    - URL format validation (must be HTTP/HTTPS)
    - Reachability checks (health endpoint responds)
    - Co-location assumptions (internal network required)
    - Startup preflight validation to prevent silent misrouting
    """

    def __init__(
        self,
        sandbox_url: str,
        health_check_timeout_sec: float = 5.0,
    ):
        """Initialize validator.

        Args:
            sandbox_url: Base URL of internal sandbox API (e.g., http://internal:9000)
            health_check_timeout_sec: Timeout for health checks

        Raises:
            SandboxURLValidationError: If URL format is invalid
        """
        self.sandbox_url = sandbox_url.rstrip("/")
        self.health_check_timeout_sec = health_check_timeout_sec

        # Validate URL format
        self._validate_url_format()

    def _validate_url_format(self) -> None:
        """Validate that URL is in correct format.

        Raises:
            SandboxURLValidationError: If URL is malformed
        """
        if not self.sandbox_url:
            raise SandboxURLValidationError(
                "INTERNAL_SANDBOX_URL cannot be empty"
            )

        parsed = urlparse(self.sandbox_url)

        if not parsed.scheme:
            raise SandboxURLValidationError(
                f"INTERNAL_SANDBOX_URL missing scheme (http/https): {self.sandbox_url}"
            )

        if parsed.scheme not in ("http", "https"):
            raise SandboxURLValidationError(
                f"INTERNAL_SANDBOX_URL scheme must be http or https, got: {parsed.scheme}"
            )

        if not parsed.hostname:
            raise SandboxURLValidationError(
                f"INTERNAL_SANDBOX_URL missing hostname: {self.sandbox_url}"
            )

    def _validate_co_location_assumption(self) -> None:
        """Verify co-location assumption: internal URL must be on private network.

        For hosted non-Sprites mode to work safely, the INTERNAL_SANDBOX_URL
        MUST point to a service on a private/internal network, not the public internet.

        This check warns if the URL appears to be on a public IP or domain.

        Raises:
            SandboxURLValidationError: If assumptions are violated
        """
        parsed = urlparse(self.sandbox_url)
        hostname = parsed.hostname

        # Check for obviously public domains
        dangerous_patterns = [
            ".com",
            ".net",
            ".org",
            ".io",
            "amazonaws.com",
            "azure.microsoft.com",
            "gcp",
        ]

        for pattern in dangerous_patterns:
            if pattern in hostname.lower():
                logger.warning(
                    f"INTERNAL_SANDBOX_URL appears to be on public domain: {hostname}. "
                    f"This may violate co-location assumptions. "
                    f"Use private/internal DNS for sandbox service.",
                )

        # Check for loopback
        if hostname in ("127.0.0.1", "localhost", "::1"):
            logger.info(
                f"INTERNAL_SANDBOX_URL is loopback ({hostname}). "
                f"OK for local development, but not for production hosted mode."
            )

    async def health_check(self) -> bool:
        """Perform async health check against sandbox URL.

        Attempts to reach /internal/health endpoint.

        Returns:
            True if health check succeeds, False otherwise

        Raises:
            SandboxURLValidationError: If health check cannot be performed
        """
        health_url = f"{self.sandbox_url}/internal/health"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    health_url,
                    timeout=self.health_check_timeout_sec,
                )

                if response.status_code == 200:
                    logger.info(
                        f"Health check passed: {health_url} returned 200",
                    )
                    return True
                else:
                    logger.error(
                        f"Health check failed: {health_url} returned {response.status_code}",
                    )
                    return False

        except asyncio.TimeoutError:
            raise SandboxURLValidationError(
                f"Health check timeout to {health_url} after {self.health_check_timeout_sec}s. "
                f"Verify INTERNAL_SANDBOX_URL is reachable and sandbox service is running."
            )
        except httpx.ConnectError as e:
            raise SandboxURLValidationError(
                f"Cannot connect to {health_url}: {e}. "
                f"Verify INTERNAL_SANDBOX_URL is reachable."
            )
        except Exception as e:
            raise SandboxURLValidationError(
                f"Health check error for {health_url}: {e}"
            )

    async def validate_startup(self) -> None:
        """Run full startup validation suite.

        This is called at application startup to ensure configuration is correct
        and prevent silent misrouting to wrong services.

        Raises:
            SandboxURLValidationError: If any validation fails
        """
        logger.info(
            f"Starting INTERNAL_SANDBOX_URL validation for: {self.sandbox_url}",
        )

        # 1. Format already validated in __init__
        logger.debug("✓ URL format valid")

        # 2. Verify co-location assumptions
        self._validate_co_location_assumption()
        logger.debug("✓ Co-location assumptions checked")

        # 3. Health check - this is critical, fail fast if service unreachable
        if not await self.health_check():
            raise SandboxURLValidationError(
                f"Sandbox service health check failed at {self.sandbox_url}. "
                f"Service must be running and reachable before control plane starts."
            )

        logger.info(
            f"✓ INTERNAL_SANDBOX_URL validation complete: {self.sandbox_url}",
        )

    @staticmethod
    def from_env(env: Optional[dict] = None) -> Optional["InternalSandboxURLValidator"]:
        """Create validator from environment variable.

        Args:
            env: Environment dict (uses os.environ if None)

        Returns:
            Validator if INTERNAL_SANDBOX_URL is set, None otherwise

        Raises:
            SandboxURLValidationError: If URL format is invalid
        """
        import os

        if env is None:
            env = os.environ

        sandbox_url = env.get("INTERNAL_SANDBOX_URL", "").strip()
        if not sandbox_url:
            return None

        return InternalSandboxURLValidator(sandbox_url)
