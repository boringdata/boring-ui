"""Tests for the orphan cleanup job."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from boring_ui.api.modules.sandbox.cleanup import cleanup_orphans, find_orphans


def _utc_iso(days_ago: int) -> str:
    """Return an ISO timestamp N days in the past."""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


def _make_client(sprites: list[dict]) -> MagicMock:
    """Create a mock SpritesClient that returns the given sprites."""
    client = MagicMock()
    client.list_sprites = AsyncMock(return_value=sprites)
    client.delete_sprite = AsyncMock()
    return client


class TestFindOrphans:
    @pytest.mark.asyncio
    async def test_no_sprites(self):
        client = _make_client([])
        result = await find_orphans(client, max_inactive_days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_all_active(self):
        sprites = [
            {"name": "s1", "last_active_at": _utc_iso(1)},
            {"name": "s2", "last_active_at": _utc_iso(5)},
        ]
        client = _make_client(sprites)
        result = await find_orphans(client, max_inactive_days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_finds_old_sprites(self):
        sprites = [
            {"name": "fresh", "last_active_at": _utc_iso(1)},
            {"name": "stale", "last_active_at": _utc_iso(45)},
        ]
        client = _make_client(sprites)
        result = await find_orphans(client, max_inactive_days=30)
        assert len(result) == 1
        assert result[0]["name"] == "stale"

    @pytest.mark.asyncio
    async def test_no_timestamp_treated_as_orphan(self):
        sprites = [{"name": "no-ts"}]
        client = _make_client(sprites)
        result = await find_orphans(client, max_inactive_days=30)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_invalid_timestamp_treated_as_orphan(self):
        sprites = [{"name": "bad-ts", "last_active_at": "not-a-date"}]
        client = _make_client(sprites)
        result = await find_orphans(client, max_inactive_days=30)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_prefix_filter(self):
        sprites = [
            {"name": "prod-s1", "last_active_at": _utc_iso(45)},
            {"name": "staging-s1", "last_active_at": _utc_iso(45)},
        ]
        client = _make_client(sprites)
        result = await find_orphans(client, max_inactive_days=30, prefix="prod-")
        assert len(result) == 1
        assert result[0]["name"] == "prod-s1"

    @pytest.mark.asyncio
    async def test_uses_created_at_fallback(self):
        sprites = [
            {"name": "s1", "created_at": _utc_iso(45)},
        ]
        client = _make_client(sprites)
        result = await find_orphans(client, max_inactive_days=30)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_z_suffix_timestamp(self):
        """Handles ISO timestamps ending with Z."""
        old = datetime.now(timezone.utc) - timedelta(days=45)
        sprites = [
            {"name": "s1", "last_active_at": old.strftime("%Y-%m-%dT%H:%M:%SZ")},
        ]
        client = _make_client(sprites)
        result = await find_orphans(client, max_inactive_days=30)
        assert len(result) == 1


class TestCleanupOrphans:
    @pytest.mark.asyncio
    async def test_dry_run_no_deletions(self):
        sprites = [
            {"name": "stale", "last_active_at": _utc_iso(45)},
        ]
        client = _make_client(sprites)
        result = await cleanup_orphans(client, max_inactive_days=30, dry_run=True)
        assert result["found"] == 1
        assert result["deleted"] == 0
        assert result["errors"] == 0
        assert "stale" in result["names"]
        client.delete_sprite.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_mode(self):
        sprites = [
            {"name": "orphan1", "last_active_at": _utc_iso(45)},
            {"name": "orphan2", "last_active_at": _utc_iso(60)},
        ]
        client = _make_client(sprites)
        result = await cleanup_orphans(client, max_inactive_days=30, dry_run=False)
        assert result["found"] == 2
        assert result["deleted"] == 2
        assert result["errors"] == 0
        assert client.delete_sprite.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_with_errors(self):
        sprites = [
            {"name": "ok", "last_active_at": _utc_iso(45)},
            {"name": "fail", "last_active_at": _utc_iso(45)},
        ]
        client = _make_client(sprites)
        client.delete_sprite.side_effect = [None, Exception("API error")]
        result = await cleanup_orphans(client, max_inactive_days=30, dry_run=False)
        assert result["found"] == 2
        assert result["deleted"] == 1
        assert result["errors"] == 1

    @pytest.mark.asyncio
    async def test_no_orphans_found(self):
        sprites = [
            {"name": "active", "last_active_at": _utc_iso(1)},
        ]
        client = _make_client(sprites)
        result = await cleanup_orphans(client, max_inactive_days=30, dry_run=False)
        assert result["found"] == 0
        assert result["deleted"] == 0
        client.delete_sprite.assert_not_called()

    @pytest.mark.asyncio
    async def test_prefix_respected_in_cleanup(self):
        sprites = [
            {"name": "prod-stale", "last_active_at": _utc_iso(45)},
            {"name": "staging-stale", "last_active_at": _utc_iso(45)},
        ]
        client = _make_client(sprites)
        result = await cleanup_orphans(
            client, max_inactive_days=30, prefix="prod-", dry_run=False,
        )
        assert result["found"] == 1
        assert result["deleted"] == 1
        client.delete_sprite.assert_called_once_with("prod-stale")
