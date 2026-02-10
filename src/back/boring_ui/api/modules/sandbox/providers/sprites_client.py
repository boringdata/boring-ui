"""Async client for Sprites.dev platform.

Provides a clean interface for interacting with Sprites.dev VMs:
- REST API for sprite CRUD and checkpoints
- CLI-based exec (Sprites exec API is WebSocket-only)
- Automatic retry with exponential backoff
- Multi-tenant name prefixing

Example::

    client = SpritesClient(token="...", org="my-org")
    sprite = await client.create_sprite("sb-alice")
    rc, out, err = await client.exec("sb-alice", "echo hello")
    await client.close()
"""
from __future__ import annotations

import logging
import shutil
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

RetryStrategy = Literal["none", "exponential"]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SpritesClientError(Exception):
    """Base exception for all SpritesClient errors."""

    pass


class SpritesCLINotFoundError(SpritesClientError):
    """Raised when the ``sprite`` CLI binary is not on PATH."""

    pass


class SpritesAPIError(SpritesClientError):
    """HTTP error from the Sprites.dev REST API.

    Attributes:
        status_code: HTTP status code (4xx or 5xx).
        message: Error detail from the API response.
    """

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Sprites API error {status_code}: {message}")


class SpritesExecError(SpritesClientError):
    """Command execution inside a sprite returned non-zero.

    Attributes:
        return_code: Process exit code.
        stdout: Standard output (may be truncated in str()).
        stderr: Standard error (may be truncated in str()).
    """

    def __init__(self, return_code: int, stdout: str, stderr: str):
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        detail = (stderr[:200] if stderr else stdout[:200]) or "(no output)"
        super().__init__(f"Command failed (exit {return_code}): {detail}")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SpritesClient:
    """Hybrid REST + CLI client for Sprites.dev.

    REST (httpx) handles sprite CRUD and checkpoints.
    CLI (asyncio subprocess) handles command execution because the
    Sprites REST exec endpoint uses WebSocket.

    Args:
        token: Sprites.dev API bearer token.
        org: Organisation slug.
        base_url: API base URL.
        cli_path: Path to the ``sprite`` CLI binary.
        name_prefix: Prefix applied to all sprite names (multi-tenant).
        retry_strategy: ``"exponential"`` for backoff or ``"none"``.
        max_retries: Maximum retry attempts for transient (5xx) errors.
    """

    def __init__(
        self,
        token: str,
        org: str,
        base_url: str = "https://api.sprites.dev",
        cli_path: str = "sprite",
        name_prefix: str = "",
        retry_strategy: RetryStrategy = "exponential",
        max_retries: int = 3,
    ):
        self._token = token
        self._org = org
        self._base_url = base_url.rstrip("/")
        self._cli_path = cli_path
        self._name_prefix = name_prefix
        self._retry_strategy = retry_strategy
        self._max_retries = max_retries

        self._verify_cli_available()

        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

        logger.info(
            "SpritesClient initialized",
            extra={
                "org": self._org,
                "base_url": self._base_url,
                "name_prefix": self._name_prefix or "(none)",
                "retry_strategy": self._retry_strategy,
            },
        )

    # ------ helpers ------

    def _verify_cli_available(self) -> None:
        """Fail fast if the sprite CLI is not installed."""
        if not shutil.which(self._cli_path):
            raise SpritesCLINotFoundError(
                f"Sprite CLI not found at '{self._cli_path}'. "
                "Install with: curl -fsSL https://sprites.dev/install.sh | sh\n"
                "Then ensure it's in your PATH."
            )

    def _prefixed_name(self, name: str) -> str:
        """Apply configured prefix to a sprite name.

        Avoids double-prefixing if the name already starts with the prefix.
        """
        if self._name_prefix and not name.startswith(self._name_prefix):
            return f"{self._name_prefix}{name}"
        return name

    # ------ lifecycle ------

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._http.aclose()
        logger.debug("SpritesClient closed")

    async def __aenter__(self) -> SpritesClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
