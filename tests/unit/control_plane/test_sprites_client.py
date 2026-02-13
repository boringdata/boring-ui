"""Unit tests for SpritesClient (bd-1joj.14).

Tests the HTTP client for Sprites.dev API with mocked httpx transport.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from control_plane.app.providers.sprites_client import (
    SpritesAPIError,
    SpritesClient,
    SpritesNotFoundError,
    SpritesTimeoutError,
    _DEFAULT_BASE_DELAY,
)


def _make_client(**kwargs) -> SpritesClient:
    return SpritesClient(
        bearer_token="test-sprite-token",
        base_url="https://api.sprites.dev",
        **kwargs,
    )


# ── Test: create_sprite sends correct HTTP request ───────────────


@pytest.mark.asyncio
async def test_create_sprite_sends_correct_http_request():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(
            201,
            json={"name": "sbx-app-ws1-dev", "state": "running"},
        )
    )

    client = _make_client(http_client=mock_http)
    result = await client.create_sprite(
        "sbx-app-ws1-dev",
        sandbox_profile="default",
        env={"API_KEY": "secret"},
    )

    assert result["name"] == "sbx-app-ws1-dev"

    # Verify the request.
    call = mock_http.request.call_args
    assert call.args[0] == "POST"
    assert "/v1/sprites" in call.args[1]
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-sprite-token"
    body = call.kwargs["json"]
    assert body["name"] == "sbx-app-ws1-dev"
    assert body["profile"] == "default"
    assert body["env"]["API_KEY"] == "secret"


# ── Test: get_sprite returns sprite data ─────────────────────────


@pytest.mark.asyncio
async def test_get_sprite_returns_sprite_data():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(
            200,
            json={"name": "sbx-app-ws1-dev", "state": "running", "ip": "10.0.0.1"},
        )
    )

    client = _make_client(http_client=mock_http)
    result = await client.get_sprite("sbx-app-ws1-dev")

    assert result["name"] == "sbx-app-ws1-dev"
    assert result["state"] == "running"

    call = mock_http.request.call_args
    assert call.args[0] == "GET"
    assert "/v1/sprites/sbx-app-ws1-dev" in call.args[1]


# ── Test: delete_sprite sends DELETE request ─────────────────────


@pytest.mark.asyncio
async def test_delete_sprite_sends_delete_request():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(204)
    )

    client = _make_client(http_client=mock_http)
    await client.delete_sprite("sbx-app-ws1-dev")

    call = mock_http.request.call_args
    assert call.args[0] == "DELETE"
    assert "/v1/sprites/sbx-app-ws1-dev" in call.args[1]


# ── Test: list_sprites with prefix ───────────────────────────────


@pytest.mark.asyncio
async def test_list_sprites_sends_prefix_param():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(
            200,
            json=[{"name": "sbx-app-ws1-dev"}, {"name": "sbx-app-ws2-dev"}],
        )
    )

    client = _make_client(http_client=mock_http)
    result = await client.list_sprites(prefix="sbx-app")

    assert len(result) == 2

    call = mock_http.request.call_args
    assert call.kwargs["params"]["prefix"] == "sbx-app"


# ── Test: 404 raises SpritesNotFoundError ────────────────────────


@pytest.mark.asyncio
async def test_404_raises_sprites_not_found_error():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(
            404,
            json={"error": "Sprite not found"},
        )
    )

    client = _make_client(http_client=mock_http)

    with pytest.raises(SpritesNotFoundError) as exc_info:
        await client.get_sprite("nonexistent")

    assert exc_info.value.status_code == 404


# ── Test: other HTTP errors raise SpritesAPIError ────────────────


@pytest.mark.asyncio
async def test_500_raises_sprites_api_error():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(
            500,
            text="Internal Server Error",
        )
    )

    client = _make_client(http_client=mock_http, max_retries=0)

    with pytest.raises(SpritesAPIError) as exc_info:
        await client.get_sprite("broken")

    assert exc_info.value.status_code == 500


# ── Test: retry on 429 respects Retry-After ──────────────────────


@pytest.mark.asyncio
async def test_retry_on_429_respects_retry_after():
    mock_http = AsyncMock()

    # First call: 429 with Retry-After, second call: 200.
    mock_http.request = AsyncMock(
        side_effect=[
            httpx.Response(
                429,
                text="Too Many Requests",
                headers={"Retry-After": "0.1"},
            ),
            httpx.Response(
                200,
                json={"name": "sbx-app-ws1-dev", "state": "running"},
            ),
        ]
    )

    with patch("control_plane.app.providers.sprites_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        client = _make_client(http_client=mock_http, max_retries=2)
        result = await client.get_sprite("sbx-app-ws1-dev")

    assert result["name"] == "sbx-app-ws1-dev"
    assert mock_http.request.call_count == 2

    # Should have used the Retry-After value.
    mock_sleep.assert_called_once()
    delay = mock_sleep.call_args.args[0]
    assert delay >= 0.1


# ── Test: retry on 502 with exponential backoff ──────────────────


@pytest.mark.asyncio
async def test_retry_on_502_with_backoff():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        side_effect=[
            httpx.Response(502, text="Bad Gateway"),
            httpx.Response(502, text="Bad Gateway"),
            httpx.Response(200, json={"name": "test"}),
        ]
    )

    with patch("control_plane.app.providers.sprites_client.asyncio.sleep", new_callable=AsyncMock):
        client = _make_client(http_client=mock_http, max_retries=3)
        result = await client.get_sprite("test")

    assert result["name"] == "test"
    assert mock_http.request.call_count == 3


# ── Test: retries exhausted returns last error ───────────────────


@pytest.mark.asyncio
async def test_retries_exhausted_returns_last_error():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(503, text="Service Unavailable"),
    )

    with patch("control_plane.app.providers.sprites_client.asyncio.sleep", new_callable=AsyncMock):
        client = _make_client(http_client=mock_http, max_retries=2)

        with pytest.raises(SpritesAPIError) as exc_info:
            await client.get_sprite("unavailable")

    assert exc_info.value.status_code == 503
    # Should have tried 3 times total (initial + 2 retries).
    assert mock_http.request.call_count == 3


# ── Test: timeout raises SpritesTimeoutError ─────────────────────


@pytest.mark.asyncio
async def test_timeout_raises_sprites_timeout_error():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        side_effect=httpx.TimeoutException("connect timeout"),
    )

    with patch("control_plane.app.providers.sprites_client.asyncio.sleep", new_callable=AsyncMock):
        client = _make_client(http_client=mock_http, max_retries=1)

        with pytest.raises(SpritesTimeoutError):
            await client.get_sprite("slow")

    # Initial + 1 retry.
    assert mock_http.request.call_count == 2


# ── Test: bearer_token required ──────────────────────────────────


def test_bearer_token_required():
    with pytest.raises(ValueError, match="bearer_token"):
        SpritesClient(bearer_token="")


# ── Test: non-retryable error not retried ────────────────────────


@pytest.mark.asyncio
async def test_non_retryable_status_not_retried():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(
            400,
            json={"error": "Bad Request"},
        )
    )

    client = _make_client(http_client=mock_http, max_retries=3)

    with pytest.raises(SpritesAPIError) as exc_info:
        await client.create_sprite("bad")

    assert exc_info.value.status_code == 400
    # Should NOT retry on 400.
    assert mock_http.request.call_count == 1


# ── Test: create_sprite without env ──────────────────────────────


@pytest.mark.asyncio
async def test_create_sprite_without_env():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(
            201,
            json={"name": "test", "state": "running"},
        )
    )

    client = _make_client(http_client=mock_http)
    await client.create_sprite("test")

    body = mock_http.request.call_args.kwargs["json"]
    assert "env" not in body


# ── Test: list_sprites without prefix ────────────────────────────


@pytest.mark.asyncio
async def test_list_sprites_without_prefix():
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(
        return_value=httpx.Response(200, json=[]),
    )

    client = _make_client(http_client=mock_http)
    result = await client.list_sprites()

    assert result == []
    call = mock_http.request.call_args
    assert call.kwargs.get("params") == {} or not call.kwargs.get("params")
