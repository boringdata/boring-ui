"""Tests for SandboxManager and create_provider factory.

Covers bd-1ni.4: factory wiring for sprites provider, config validation.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from boring_ui.api.modules.sandbox.manager import SandboxManager, create_provider
from boring_ui.api.modules.sandbox.providers.local import LocalProvider


class TestCreateProviderLocal:
    def test_default_is_local(self):
        provider = create_provider({})
        assert isinstance(provider, LocalProvider)

    def test_local_explicit(self):
        provider = create_provider({"SANDBOX_PROVIDER": "local"})
        assert isinstance(provider, LocalProvider)

    def test_local_custom_port(self):
        provider = create_provider({"SANDBOX_PORT": "3000"})
        assert provider.port == 3000


class TestCreateProviderSprites:
    @patch("shutil.which", return_value="/usr/bin/sprite")
    def test_sprites_creates_provider(self, mock_which):
        from boring_ui.api.modules.sandbox.providers.sprites import SpritesProvider

        provider = create_provider({
            "SANDBOX_PROVIDER": "sprites",
            "SPRITES_TOKEN": "tok",
            "SPRITES_ORG": "my-org",
        })
        assert isinstance(provider, SpritesProvider)

    @patch("shutil.which", return_value="/usr/bin/sprite")
    def test_sprites_with_prefix(self, mock_which):
        provider = create_provider({
            "SANDBOX_PROVIDER": "sprites",
            "SPRITES_TOKEN": "tok",
            "SPRITES_ORG": "my-org",
            "SPRITES_NAME_PREFIX": "sb-",
        })
        assert provider._client._name_prefix == "sb-"

    @patch("shutil.which", return_value="/usr/bin/sprite")
    def test_sprites_custom_port(self, mock_which):
        provider = create_provider({
            "SANDBOX_PROVIDER": "sprites",
            "SPRITES_TOKEN": "tok",
            "SPRITES_ORG": "my-org",
            "SANDBOX_PORT": "3000",
        })
        assert provider._port == 3000

    def test_sprites_missing_token(self):
        with pytest.raises(ValueError, match="SPRITES_TOKEN"):
            create_provider({
                "SANDBOX_PROVIDER": "sprites",
                "SPRITES_ORG": "my-org",
            })

    def test_sprites_missing_org(self):
        with pytest.raises(ValueError, match="SPRITES_ORG"):
            create_provider({
                "SANDBOX_PROVIDER": "sprites",
                "SPRITES_TOKEN": "tok",
            })

    def test_sprites_empty_token(self):
        with pytest.raises(ValueError, match="SPRITES_TOKEN"):
            create_provider({
                "SANDBOX_PROVIDER": "sprites",
                "SPRITES_TOKEN": "",
                "SPRITES_ORG": "my-org",
            })


class TestCreateProviderUnknown:
    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown sandbox provider"):
            create_provider({"SANDBOX_PROVIDER": "docker"})


class TestSandboxManager:
    @pytest.mark.asyncio
    async def test_ensure_running_returns_existing(self):
        from unittest.mock import AsyncMock
        from boring_ui.api.modules.sandbox.provider import SandboxInfo

        provider = AsyncMock()
        provider.get_info.return_value = SandboxInfo(
            id="default", base_url="http://localhost:2468",
            status="running", workspace_path="/tmp", provider="local",
        )
        manager = SandboxManager(provider)
        info = await manager.ensure_running()
        assert info.status == "running"
        provider.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_running_creates_if_missing(self):
        from unittest.mock import AsyncMock
        from boring_ui.api.modules.sandbox.provider import SandboxInfo

        provider = AsyncMock()
        provider.get_info.return_value = None
        provider.create.return_value = SandboxInfo(
            id="default", base_url="http://localhost:2468",
            status="running", workspace_path="/tmp", provider="local",
        )
        manager = SandboxManager(provider)
        info = await manager.ensure_running()
        assert info.status == "running"
        provider.create.assert_called_once()
