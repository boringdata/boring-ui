"""Tests for target resolver interfaces (bd-1adh.3.2)."""

import pytest
import os
from unittest.mock import patch
from boring_ui.api.target_resolver import (
    WorkspaceTarget,
    StaticTargetResolver,
)


class TestWorkspaceTarget:
    """Tests for WorkspaceTarget dataclass validation."""

    def test_sprites_target_valid(self):
        """Sprites target with sprite_name and port is valid."""
        target = WorkspaceTarget(
            provider="sprites",
            sprite_name="test-sprite",
            local_api_port=8001,
        )
        assert target.provider == "sprites"
        assert target.sprite_name == "test-sprite"
        assert target.local_api_port == 8001
        assert target.internal_base_url is None

    def test_sprites_target_missing_sprite_name(self):
        """Sprites target without sprite_name raises ValueError."""
        with pytest.raises(ValueError, match="sprite_name"):
            WorkspaceTarget(
                provider="sprites",
                sprite_name=None,
                local_api_port=8001,
            )

    def test_sprites_target_missing_port(self):
        """Sprites target without local_api_port raises ValueError."""
        with pytest.raises(ValueError, match="local_api_port"):
            WorkspaceTarget(
                provider="sprites",
                sprite_name="test-sprite",
                local_api_port=None,
            )

    def test_sprites_target_with_internal_url(self):
        """Sprites target with internal_base_url raises ValueError."""
        with pytest.raises(ValueError, match="internal_base_url"):
            WorkspaceTarget(
                provider="sprites",
                sprite_name="test-sprite",
                local_api_port=8001,
                internal_base_url="http://example.com",
            )

    def test_non_sprites_target_valid(self):
        """Non-Sprites target with internal_base_url is valid."""
        target = WorkspaceTarget(
            provider="sandbox",
            internal_base_url="http://localhost:9000",
        )
        assert target.provider == "sandbox"
        assert target.internal_base_url == "http://localhost:9000"
        assert target.sprite_name is None
        assert target.local_api_port is None

    def test_non_sprites_target_missing_url(self):
        """Non-Sprites target without internal_base_url raises ValueError."""
        with pytest.raises(ValueError, match="internal_base_url"):
            WorkspaceTarget(
                provider="sandbox",
                internal_base_url=None,
            )

    def test_non_sprites_target_with_sprite_name(self):
        """Non-Sprites target with sprite_name raises ValueError."""
        with pytest.raises(ValueError, match="sprite_name"):
            WorkspaceTarget(
                provider="sandbox",
                sprite_name="test-sprite",
                internal_base_url="http://localhost:9000",
            )


class TestStaticTargetResolver:
    """Tests for StaticTargetResolver."""

    @patch.dict(os.environ, {
        "SPRITES_TARGET_SPRITE": "prod-sprite",
        "SPRITES_LOCAL_API_PORT": "8001",
    })
    def test_sprites_resolver_init(self):
        """Sprites resolver initializes with env vars."""
        resolver = StaticTargetResolver(provider="sprites")
        assert resolver.provider == "sprites"
        assert resolver.sprite_name == "prod-sprite"
        assert resolver.local_api_port == 8001
        assert resolver.internal_base_url is None

    @patch.dict(os.environ, {}, clear=True)
    def test_sprites_resolver_missing_sprite_name(self):
        """Sprites resolver without SPRITES_TARGET_SPRITE raises ValueError."""
        with pytest.raises(ValueError, match="SPRITES_TARGET_SPRITE"):
            StaticTargetResolver(provider="sprites")

    @patch.dict(os.environ, {
        "SPRITES_TARGET_SPRITE": "prod-sprite",
        "SPRITES_LOCAL_API_PORT": "not-a-number",
    })
    def test_sprites_resolver_invalid_port(self):
        """Sprites resolver with non-integer port raises ValueError."""
        with pytest.raises(ValueError, match="integer"):
            StaticTargetResolver(provider="sprites")

    @patch.dict(os.environ, {
        "SPRITES_TARGET_SPRITE": "prod-sprite",
        "SPRITES_LOCAL_API_PORT": "9001",
    })
    def test_sprites_resolver_default_port(self):
        """Sprites resolver defaults to port 8001."""
        del os.environ["SPRITES_LOCAL_API_PORT"]
        resolver = StaticTargetResolver(provider="sprites")
        assert resolver.local_api_port == 8001

    @patch.dict(os.environ, {
        "INTERNAL_SANDBOX_URL": "http://internal.local:9000",
    })
    def test_non_sprites_resolver_init(self):
        """Non-Sprites resolver initializes with env var."""
        resolver = StaticTargetResolver(provider="sandbox")
        assert resolver.provider == "sandbox"
        assert resolver.internal_base_url == "http://internal.local:9000"
        assert resolver.sprite_name is None
        assert resolver.local_api_port is None

    @patch.dict(os.environ, {}, clear=True)
    def test_non_sprites_resolver_missing_url(self):
        """Non-Sprites resolver without INTERNAL_SANDBOX_URL raises ValueError."""
        with pytest.raises(ValueError, match="INTERNAL_SANDBOX_URL"):
            StaticTargetResolver(provider="sandbox")

    @pytest.mark.asyncio
    @patch.dict(os.environ, {
        "SPRITES_TARGET_SPRITE": "test-sprite",
        "SPRITES_LOCAL_API_PORT": "8001",
    })
    async def test_sprites_resolver_resolve(self):
        """Sprites resolver.resolve() returns WorkspaceTarget."""
        resolver = StaticTargetResolver(provider="sprites")
        target = await resolver.resolve(
            workspace_id="ws-123",
            user_id="user-456",
        )

        assert target.provider == "sprites"
        assert target.sprite_name == "test-sprite"
        assert target.local_api_port == 8001
        assert target.internal_base_url is None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {
        "INTERNAL_SANDBOX_URL": "http://localhost:9000",
    })
    async def test_non_sprites_resolver_resolve(self):
        """Non-Sprites resolver.resolve() returns WorkspaceTarget."""
        resolver = StaticTargetResolver(provider="sandbox")
        target = await resolver.resolve(
            workspace_id="ws-123",
            user_id="user-456",
        )

        assert target.provider == "sandbox"
        assert target.internal_base_url == "http://localhost:9000"
        assert target.sprite_name is None
        assert target.local_api_port is None

    @pytest.mark.asyncio
    @patch.dict(os.environ, {
        "SPRITES_TARGET_SPRITE": "test-sprite",
        "SPRITES_LOCAL_API_PORT": "8001",
    })
    async def test_resolver_ignores_workspace_and_user(self):
        """Static resolver ignores workspace_id and user_id (hardcoded)."""
        resolver = StaticTargetResolver(provider="sprites")

        # Multiple calls with different inputs should return same target
        target1 = await resolver.resolve("ws-111", "user-aaa")
        target2 = await resolver.resolve("ws-222", "user-bbb")
        target3 = await resolver.resolve("ws-333", None)

        assert target1 == target2 == target3
