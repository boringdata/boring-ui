"""Unit tests for SpriteSandboxProvider (bd-1joj.14).

Tests the SandboxProvider implementation backed by SpritesClient.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from control_plane.app.providers.sprite_provider import (
    SpriteSandboxProvider,
    build_sandbox_name,
    _slugify,
)
from control_plane.app.providers.sprites_client import (
    SpritesAPIError,
    SpritesClient,
    SpritesNotFoundError,
)


def _make_provider(client: AsyncMock | None = None) -> SpriteSandboxProvider:
    if client is None:
        client = AsyncMock(spec=SpritesClient)
    return SpriteSandboxProvider(client)


# ── Test: sandbox name normalization ─────────────────────────────


def test_sandbox_name_normalization():
    """sbx-{app_id}-{workspace_id}-{env} with slug normalization."""
    assert build_sandbox_name("boring-ui", "ws_1", "dev") == "sbx-boring-ui-ws-1-dev"
    assert build_sandbox_name("Boring UI", "WS_ABC", "Prod") == "sbx-boring-ui-ws-abc-prod"
    assert build_sandbox_name("my--app", "ws@123", "dev") == "sbx-my-app-ws-123-dev"


def test_sandbox_name_default_env():
    assert build_sandbox_name("app", "ws1") == "sbx-app-ws1-dev"


def test_slugify_edge_cases():
    assert _slugify("Hello World") == "hello-world"
    assert _slugify("--dash--") == "dash"
    assert _slugify("UPPER") == "upper"
    assert _slugify("a.b.c") == "a-b-c"
    assert _slugify("already-good") == "already-good"


# ── Test: create_sandbox calls SpritesClient.create_sprite ───────


@pytest.mark.asyncio
async def test_create_sandbox_calls_sprites_client():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.create_sprite = AsyncMock(
        return_value={"name": "sbx-app-ws1-dev", "state": "running", "ip": "10.0.0.1"},
    )

    provider = _make_provider(mock_client)
    result = await provider.create_sandbox(
        "sbx-app-ws1-dev",
        workspace_id="ws1",
        app_id="app",
    )

    mock_client.create_sprite.assert_called_once_with(
        "sbx-app-ws1-dev",
        sandbox_profile="default",
        env=None,
    )
    assert result["name"] == "sbx-app-ws1-dev"
    assert result["state"] == "running"
    assert result["runtime_url"] == "https://sbx-app-ws1-dev.sprites.dev"


# ── Test: create_sandbox passes sandbox_profile and env ──────────


@pytest.mark.asyncio
async def test_create_sandbox_passes_profile_and_env():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.create_sprite = AsyncMock(return_value={"name": "test"})

    provider = _make_provider(mock_client)
    await provider.create_sandbox(
        "test",
        sandbox_profile="gpu",
        env={"KEY": "val"},
    )

    call = mock_client.create_sprite.call_args
    assert call.kwargs["sandbox_profile"] == "gpu"
    assert call.kwargs["env"] == {"KEY": "val"}


# ── Test: get_sandbox returns metadata with runtime_url ──────────


@pytest.mark.asyncio
async def test_get_sandbox_returns_metadata():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.get_sprite = AsyncMock(
        return_value={"name": "sbx-app-ws1-dev", "state": "running"},
    )

    provider = _make_provider(mock_client)
    result = await provider.get_sandbox("sbx-app-ws1-dev")

    assert result is not None
    assert result["runtime_url"] == "https://sbx-app-ws1-dev.sprites.dev"
    assert result["state"] == "running"


# ── Test: get_sandbox returns None for missing sprite ────────────


@pytest.mark.asyncio
async def test_get_sandbox_returns_none_when_not_found():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.get_sprite = AsyncMock(side_effect=SpritesNotFoundError())

    provider = _make_provider(mock_client)
    result = await provider.get_sandbox("nonexistent")

    assert result is None


# ── Test: health_check returns True for running sandbox ──────────


@pytest.mark.asyncio
async def test_health_check_returns_true_for_running():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.get_sprite = AsyncMock(
        return_value={"state": "running"},
    )

    provider = _make_provider(mock_client)
    assert await provider.health_check("sbx-app-ws1-dev") is True


# ── Test: health_check returns False for missing sandbox ─────────


@pytest.mark.asyncio
async def test_health_check_returns_false_for_missing():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.get_sprite = AsyncMock(side_effect=SpritesNotFoundError())

    provider = _make_provider(mock_client)
    assert await provider.health_check("nonexistent") is False


# ── Test: health_check returns False on API error ────────────────


@pytest.mark.asyncio
async def test_health_check_returns_false_on_api_error():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.get_sprite = AsyncMock(
        side_effect=SpritesAPIError(500, "Internal error"),
    )

    provider = _make_provider(mock_client)
    assert await provider.health_check("broken") is False


# ── Test: delete_sandbox calls SpritesClient.delete_sprite ───────


@pytest.mark.asyncio
async def test_delete_sandbox_calls_client():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.delete_sprite = AsyncMock()

    provider = _make_provider(mock_client)
    await provider.delete_sandbox("sbx-app-ws1-dev")

    mock_client.delete_sprite.assert_called_once_with("sbx-app-ws1-dev")


# ── Test: delete_sandbox is idempotent (ignores 404) ────────────


@pytest.mark.asyncio
async def test_delete_sandbox_idempotent_on_not_found():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.delete_sprite = AsyncMock(side_effect=SpritesNotFoundError())

    provider = _make_provider(mock_client)
    # Should not raise.
    await provider.delete_sandbox("already-gone")


# ── Test: get_runtime_url returns URL for existing sandbox ───────


@pytest.mark.asyncio
async def test_get_runtime_url_returns_url():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.get_sprite = AsyncMock(
        return_value={"name": "sbx-app-ws1-dev", "state": "running"},
    )

    provider = _make_provider(mock_client)
    url = await provider.get_runtime_url("sbx-app-ws1-dev")

    assert url == "https://sbx-app-ws1-dev.sprites.dev"


# ── Test: get_runtime_url returns None for missing sandbox ───────


@pytest.mark.asyncio
async def test_get_runtime_url_returns_none_when_not_found():
    mock_client = AsyncMock(spec=SpritesClient)
    mock_client.get_sprite = AsyncMock(side_effect=SpritesNotFoundError())

    provider = _make_provider(mock_client)
    url = await provider.get_runtime_url("nonexistent")

    assert url is None


# ── Test: protocol conformance ───────────────────────────────────


def test_protocol_conformance():
    """SpriteSandboxProvider has the methods required by SandboxProvider protocol."""
    from control_plane.app.protocols import SandboxProvider

    mock_client = AsyncMock(spec=SpritesClient)
    provider = SpriteSandboxProvider(mock_client)

    # Check protocol methods exist.
    assert hasattr(provider, "create_sandbox")
    assert hasattr(provider, "get_sandbox")
    assert hasattr(provider, "health_check")
    assert callable(provider.create_sandbox)
    assert callable(provider.get_sandbox)
    assert callable(provider.health_check)
