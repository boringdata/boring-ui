"""Async HTTP client for the Sprites.dev API.

Bead: bd-1joj.14 (SPR0)

Provides create, get, delete, and list operations against the Sprites.dev REST API.
Auth uses a static bearer token (server-side only, never leaves control plane).
Includes exponential backoff with jitter for transient errors and Retry-After
header respect for 429 responses.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Status codes eligible for automatic retry.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Default retry configuration.
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BASE_DELAY = 1.0  # seconds
_DEFAULT_MAX_DELAY = 30.0  # seconds


# ── Exception hierarchy ─────────────────────────────────────────


class SpritesAPIError(Exception):
    """Base exception for Sprites.dev API errors."""

    def __init__(
        self,
        status_code: int,
        message: str = "",
        *,
        response_body: str = "",
    ) -> None:
        self.status_code = status_code
        self.message = message
        self.response_body = response_body
        super().__init__(f"Sprites API error {status_code}: {message}")


class SpritesNotFoundError(SpritesAPIError):
    """Sprite not found (404)."""

    def __init__(self, message: str = "Sprite not found", **kwargs: Any) -> None:
        super().__init__(404, message, **kwargs)


class SpritesTimeoutError(SpritesAPIError):
    """Request to Sprites.dev timed out."""

    def __init__(self, message: str = "Request timed out") -> None:
        super().__init__(0, message)


# ── Module-level shared client ───────────────────────────────────

_shared_async_client: httpx.AsyncClient | None = None


def _get_shared_async_client() -> httpx.AsyncClient:
    global _shared_async_client
    if _shared_async_client is None:
        _shared_async_client = httpx.AsyncClient()
    return _shared_async_client


def _reset_shared_async_client_for_tests() -> None:
    global _shared_async_client
    _shared_async_client = None


# ── Client ───────────────────────────────────────────────────────


class SpritesClient:
    """Async HTTP client for Sprites.dev sandbox API.

    All calls authenticate via a static bearer token injected server-side.
    """

    def __init__(
        self,
        *,
        bearer_token: str,
        base_url: str = "https://api.sprites.dev",
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_delay: float = _DEFAULT_BASE_DELAY,
        max_delay: float = _DEFAULT_MAX_DELAY,
    ) -> None:
        if not bearer_token:
            raise ValueError("bearer_token is required")

        self._bearer_token = bearer_token
        self._base_url = base_url.rstrip("/")
        self._client = http_client or _get_shared_async_client()
        self._timeout = float(timeout_seconds)
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._bearer_token}"}

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return

        body = resp.text
        message = body[:200] if body else f"HTTP {resp.status_code}"

        try:
            payload = resp.json()
            if isinstance(payload, dict):
                message = payload.get("error", payload.get("message", message))
        except (ValueError, KeyError):
            pass

        if resp.status_code == 404:
            raise SpritesNotFoundError(message=message, response_body=body)

        raise SpritesAPIError(
            status_code=resp.status_code,
            message=message,
            response_body=body,
        )

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request with exponential backoff retry for transient errors."""
        url = f"{self._base_url}{path}"
        headers = self._auth_headers()

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    params=params,
                    timeout=self._timeout,
                )
            except httpx.TimeoutException as e:
                last_exc = SpritesTimeoutError(str(e))
                if attempt < self._max_retries:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "Sprites request timeout (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        self._max_retries + 1,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise last_exc from e

            if resp.status_code not in _RETRYABLE_STATUS_CODES:
                return resp

            # Retryable status — compute delay.
            if attempt < self._max_retries:
                delay = self._retry_after_delay(resp, attempt)
                logger.warning(
                    "Sprites %s %s returned %d (attempt %d/%d), retrying in %.1fs",
                    method,
                    path,
                    resp.status_code,
                    attempt + 1,
                    self._max_retries + 1,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                return resp

        # Should not reach here, but guard against it.
        if last_exc:
            raise last_exc
        raise SpritesAPIError(0, "exhausted retries with no response")

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with full jitter."""
        delay = min(self._base_delay * (2 ** attempt), self._max_delay)
        return random.uniform(0, delay)

    def _retry_after_delay(self, resp: httpx.Response, attempt: int) -> float:
        """Use Retry-After header if present, otherwise exponential backoff."""
        retry_after = resp.headers.get("retry-after")
        if retry_after:
            try:
                return max(float(retry_after), 0.1)
            except ValueError:
                pass
        return self._backoff_delay(attempt)

    # ── Public API ───────────────────────────────────────────────

    async def create_sprite(
        self,
        name: str,
        *,
        sandbox_profile: str = "default",
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a new Sprite sandbox.

        Returns the created sprite metadata from the API.
        """
        payload: dict[str, Any] = {
            "name": name,
            "profile": sandbox_profile,
        }
        if env:
            payload["env"] = env

        resp = await self._request_with_retry("POST", "/v1/sprites", json=payload)
        self._raise_for_status(resp)

        result = resp.json()
        logger.info(
            "Sprite created: name=%s",
            name,
            extra={"sandbox_name": name},
        )
        return result

    async def get_sprite(self, name: str) -> dict[str, Any]:
        """Get sprite metadata by name.

        Raises SpritesNotFoundError if the sprite doesn't exist.
        """
        resp = await self._request_with_retry("GET", f"/v1/sprites/{name}")
        self._raise_for_status(resp)
        return resp.json()

    async def delete_sprite(self, name: str) -> None:
        """Delete a sprite sandbox.

        Raises SpritesNotFoundError if the sprite doesn't exist.
        """
        resp = await self._request_with_retry("DELETE", f"/v1/sprites/{name}")
        self._raise_for_status(resp)
        logger.info(
            "Sprite deleted: name=%s",
            name,
            extra={"sandbox_name": name},
        )

    async def list_sprites(self, prefix: str | None = None) -> list[dict[str, Any]]:
        """List sprites, optionally filtered by name prefix."""
        params: dict[str, str] = {}
        if prefix:
            params["prefix"] = prefix

        resp = await self._request_with_retry("GET", "/v1/sprites", params=params)
        self._raise_for_status(resp)

        result = resp.json()
        if not isinstance(result, list):
            raise SpritesAPIError(
                status_code=0,
                message=f"Expected list from /v1/sprites, got {type(result).__name__}",
            )
        return result
