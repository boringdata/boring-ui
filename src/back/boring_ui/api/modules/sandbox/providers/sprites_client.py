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

import asyncio
import logging
import random
import shutil
from typing import Any, Literal

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

    # ------ retry ------

    _RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        operation: str = "",
        safe_to_retry: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send an HTTP request with optional exponential-backoff retry.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: URL path relative to base_url.
            operation: Human-readable label for logging.
            safe_to_retry: If False and strategy is "exponential",
                retries are skipped (non-idempotent operations).
            **kwargs: Forwarded to ``httpx.AsyncClient.request``.

        Returns:
            The successful httpx.Response.

        Raises:
            SpritesAPIError: On non-retryable HTTP errors or exhausted retries.
        """
        max_attempts = (
            self._max_retries
            if self._retry_strategy == "exponential" and safe_to_retry
            else 1
        )
        last_exc: Exception | None = None
        op_label = operation or f"{method} {path}"

        for attempt in range(1, max_attempts + 1):
            try:
                resp = await self._http.request(method, path, **kwargs)

                if resp.status_code < 400:
                    return resp

                if resp.status_code in self._RETRYABLE_STATUS and attempt < max_attempts:
                    sleep_s = self._backoff_delay(attempt, resp)
                    logger.warning(
                        "Retryable error, backing off",
                        extra={
                            "operation": op_label,
                            "attempt": attempt,
                            "status_code": resp.status_code,
                            "sleep_ms": int(sleep_s * 1000),
                        },
                    )
                    await asyncio.sleep(sleep_s)
                    continue

                raise SpritesAPIError(resp.status_code, resp.text[:500])

            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < max_attempts:
                    sleep_s = self._backoff_delay(attempt)
                    logger.warning(
                        "Connection error, backing off",
                        extra={
                            "operation": op_label,
                            "attempt": attempt,
                            "error": str(exc)[:200],
                            "sleep_ms": int(sleep_s * 1000),
                        },
                    )
                    await asyncio.sleep(sleep_s)
                    continue
                raise SpritesAPIError(0, f"Connection failed: {exc}") from exc

        # Should not reach here, but guard
        raise SpritesAPIError(0, f"Retry exhausted: {last_exc}")  # pragma: no cover

    def _backoff_delay(
        self, attempt: int, response: httpx.Response | None = None
    ) -> float:
        """Calculate delay with jitter, respecting Retry-After if present."""
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    return max(0.0, min(float(retry_after), 60.0))
                except ValueError:
                    pass
        base = 2 ** (attempt - 1)
        return base + random.uniform(0, base * 0.5)

    # ------ sprite CRUD ------

    async def create_sprite(self, name: str) -> dict:
        """Create a new sprite or return existing (idempotent).

        Args:
            name: Sprite name (prefix applied automatically).

        Returns:
            Sprite metadata from the API.
        """
        prefixed = self._prefixed_name(name)
        resp = await self._request_with_retry(
            "POST",
            f"/orgs/{self._org}/sprites",
            operation="create_sprite",
            json={"name": prefixed},
        )
        return resp.json()

    async def get_sprite(self, name: str) -> dict:
        """Get sprite metadata.

        Args:
            name: Sprite name (prefix applied automatically).

        Returns:
            Sprite metadata dict.

        Raises:
            SpritesAPIError: If sprite not found (404) or other error.
        """
        prefixed = self._prefixed_name(name)
        resp = await self._request_with_retry(
            "GET",
            f"/orgs/{self._org}/sprites/{prefixed}",
            operation="get_sprite",
        )
        return resp.json()

    async def delete_sprite(self, name: str) -> None:
        """Delete a sprite permanently.

        Args:
            name: Sprite name (prefix applied automatically).

        Raises:
            SpritesAPIError: On error (404 is treated as success).
        """
        prefixed = self._prefixed_name(name)
        try:
            await self._request_with_retry(
                "DELETE",
                f"/orgs/{self._org}/sprites/{prefixed}",
                operation="delete_sprite",
            )
        except SpritesAPIError as e:
            if e.status_code != 404:
                raise

    async def list_sprites(self) -> list[dict]:
        """List all sprites in the org.

        Returns:
            List of sprite metadata dicts.
        """
        resp = await self._request_with_retry(
            "GET",
            f"/orgs/{self._org}/sprites",
            operation="list_sprites",
        )
        return resp.json()

    # ------ exec ------

    async def exec(
        self, name: str, command: str, *, timeout: float = 120.0
    ) -> tuple[int, str, str]:
        """Execute a shell command inside a sprite via the CLI.

        Uses the ``sprite`` CLI because the Sprites.dev exec API
        is WebSocket-only.

        Args:
            name: Sprite name (prefix applied automatically).
            command: Shell command to execute.
            timeout: Max seconds to wait for the command.

        Returns:
            Tuple of (return_code, stdout, stderr).

        Raises:
            SpritesExecError: If command exits non-zero.
            asyncio.TimeoutError: If timeout exceeded.
        """
        prefixed = self._prefixed_name(name)
        proc = await asyncio.create_subprocess_exec(
            self._cli_path,
            "exec",
            "--org",
            self._org,
            prefixed,
            "--",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        rc = proc.returncode or 0

        if rc != 0:
            raise SpritesExecError(rc, stdout, stderr)

        return rc, stdout, stderr

    # ------ checkpoints ------

    async def create_checkpoint(self, name: str, label: str = "") -> dict:
        """Create a checkpoint of a sprite's state.

        Args:
            name: Sprite name (prefix applied automatically).
            label: Optional human-readable label.

        Returns:
            Checkpoint metadata from the API.
        """
        prefixed = self._prefixed_name(name)
        body: dict[str, str] = {}
        if label:
            body["label"] = label
        resp = await self._request_with_retry(
            "POST",
            f"/orgs/{self._org}/sprites/{prefixed}/checkpoints",
            operation="create_checkpoint",
            safe_to_retry=False,
            json=body,
        )
        return resp.json()

    async def list_checkpoints(self, name: str) -> list[dict]:
        """List checkpoints for a sprite.

        Args:
            name: Sprite name (prefix applied automatically).

        Returns:
            List of checkpoint metadata dicts.
        """
        prefixed = self._prefixed_name(name)
        resp = await self._request_with_retry(
            "GET",
            f"/orgs/{self._org}/sprites/{prefixed}/checkpoints",
            operation="list_checkpoints",
        )
        return resp.json()

    async def restore_checkpoint(
        self, name: str, checkpoint_id: str
    ) -> dict:
        """Restore a sprite to a previous checkpoint.

        Args:
            name: Sprite name (prefix applied automatically).
            checkpoint_id: ID of the checkpoint to restore.

        Returns:
            Restore result from the API.
        """
        prefixed = self._prefixed_name(name)
        resp = await self._request_with_retry(
            "POST",
            f"/orgs/{self._org}/sprites/{prefixed}/checkpoints/{checkpoint_id}/restore",
            operation="restore_checkpoint",
            safe_to_retry=False,
        )
        return resp.json()
