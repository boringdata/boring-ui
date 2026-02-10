"""Tests for SpritesProvider.

Covers bd-1ni.3.1 through bd-1ni.3.6: skeleton, create, destroy/get_info,
health/logs, checkpoints, update_credentials.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from boring_ui.api.modules.sandbox.providers.sprites import SpritesProvider
from boring_ui.api.modules.sandbox.providers.sprites_client import (
    SpritesAPIError,
    SpritesClient,
    SpritesExecError,
)


# ─────────────────────── helpers ───────────────────────


def _mock_client(**overrides) -> SpritesClient:
    """Create a mock SpritesClient with sensible defaults."""
    client = AsyncMock(spec=SpritesClient)
    client.create_sprite = AsyncMock(
        return_value={"name": "sb-user1", "status": "running", "url": "https://sb-user1.sprites.app"}
    )
    client.get_sprite = AsyncMock(
        return_value={"name": "sb-user1", "status": "running", "url": "https://sb-user1.sprites.app"}
    )
    client.delete_sprite = AsyncMock()
    client.exec = AsyncMock(return_value=(0, "", ""))
    client.create_checkpoint = AsyncMock(return_value={"id": "chk-1", "label": "test"})
    client.list_checkpoints = AsyncMock(return_value=[{"id": "chk-1"}, {"id": "chk-2"}])
    client.restore_checkpoint = AsyncMock(return_value={"status": "restored"})
    for key, val in overrides.items():
        setattr(client, key, val)
    return client


def _make_provider(**overrides) -> SpritesProvider:
    """Create a SpritesProvider with a mock client."""
    client = overrides.pop("client", _mock_client())
    return SpritesProvider(client=client, **overrides)


# ─────────────────────── Init ───────────────────────


class TestInit:
    def test_with_injected_client(self):
        client = _mock_client()
        provider = SpritesProvider(client=client)
        assert provider._client is client

    def test_requires_token_or_client(self):
        with pytest.raises(ValueError, match="client or token"):
            SpritesProvider()

    def test_with_token_creates_client(self):
        with patch("shutil.which", return_value="/usr/bin/sprite"):
            provider = SpritesProvider(token="tok", org="my-org")
        assert provider._client is not None

    def test_default_values(self):
        provider = _make_provider()
        assert provider._default_agent == "claude"
        assert provider._port == 2468
        assert provider._setup_timeout == 180.0
        assert provider._health_check_timeout == 30.0

    def test_custom_values(self):
        provider = _make_provider(
            default_agent="codex",
            sandbox_agent_port=3000,
            setup_timeout=60.0,
            health_check_timeout=10.0,
        )
        assert provider._default_agent == "codex"
        assert provider._port == 3000


# ─────────────────────── _build_env_exports ───────────────────────


class TestBuildEnvExports:
    def test_api_key_only(self):
        provider = _make_provider()
        result = provider._build_env_exports(anthropic_api_key="sk-test")
        assert "export ANTHROPIC_API_KEY=" in result
        assert "sk-test" in result

    def test_oauth_only(self):
        provider = _make_provider()
        result = provider._build_env_exports(oauth_token="tok-123")
        assert "export CLAUDE_CODE_OAUTH_TOKEN=" in result
        assert "tok-123" in result

    def test_both(self):
        provider = _make_provider()
        result = provider._build_env_exports(
            anthropic_api_key="key", oauth_token="tok",
        )
        assert "ANTHROPIC_API_KEY" in result
        assert "CLAUDE_CODE_OAUTH_TOKEN" in result

    def test_none(self):
        provider = _make_provider()
        result = provider._build_env_exports()
        assert result == ""

    def test_shell_escaping(self):
        provider = _make_provider()
        result = provider._build_env_exports(
            anthropic_api_key="key;rm -rf /",
        )
        # shlex.quote should wrap or escape the dangerous chars
        assert ";" not in result.split("=", 1)[1].split("'")[0] or "'" in result


# ─────────────────────── create ───────────────────────


class TestCreate:
    @pytest.mark.asyncio
    async def test_basic_create(self):
        provider = _make_provider()
        info = await provider.create("sb-user1", {})
        assert info.id == "sb-user1"
        assert info.provider == "sprites"
        assert info.status == "running"

    @pytest.mark.asyncio
    async def test_create_with_credentials(self):
        client = _mock_client()
        provider = SpritesProvider(client=client)
        info = await provider.create("sb-user1", {
            "anthropic_api_key": "sk-test",
        })
        assert info.id == "sb-user1"
        # Should have called exec to write credentials
        assert client.exec.call_count >= 1

    @pytest.mark.asyncio
    async def test_create_with_service_auth(self):
        client = _mock_client()
        provider = SpritesProvider(client=client)
        await provider.create("sb-user1", {
            "service_auth_secret": "secret123",
            "cors_origin": "https://example.com",
        })
        # Should have called exec for secret and cors_origin
        assert client.exec.call_count >= 2

    @pytest.mark.asyncio
    async def test_create_with_repo(self):
        client = _mock_client()
        provider = SpritesProvider(client=client)
        await provider.create("sb-user1", {
            "repo_url": "https://github.com/org/repo.git",
            "branch": "main",
        })
        # Should have called exec for git clone
        exec_calls = [str(c) for c in client.exec.call_args_list]
        assert any("git clone" in c for c in exec_calls)

    @pytest.mark.asyncio
    async def test_create_sprite_api_failure(self):
        client = _mock_client()
        client.create_sprite = AsyncMock(
            side_effect=SpritesAPIError(500, "server error")
        )
        provider = SpritesProvider(client=client)
        from boring_ui.api.modules.sandbox.errors import SandboxProvisionError
        with pytest.raises(SandboxProvisionError):
            await provider.create("sb-user1", {})

    @pytest.mark.asyncio
    async def test_create_credential_failure_nonfatal(self):
        """Credential write failure should not prevent creation."""
        client = _mock_client()
        client.exec = AsyncMock(side_effect=SpritesExecError(1, "", "permission denied"))
        provider = SpritesProvider(client=client)
        # Should not raise despite exec failure
        info = await provider.create("sb-user1", {"anthropic_api_key": "key"})
        assert info.id == "sb-user1"

    @pytest.mark.asyncio
    async def test_create_returns_sandbox_info(self):
        provider = _make_provider()
        info = await provider.create("sb-user1", {})
        assert info.protocol == "rest+sse"
        assert info.workspace_path == "/home/sprite/workspace"


# ─────────────────────── destroy ───────────────────────


class TestDestroy:
    @pytest.mark.asyncio
    async def test_destroy(self):
        client = _mock_client()
        provider = SpritesProvider(client=client)
        await provider.destroy("sb-user1")
        client.delete_sprite.assert_called_once_with("sb-user1")


# ─────────────────────── get_info ───────────────────────


class TestGetInfo:
    @pytest.mark.asyncio
    async def test_get_info_exists(self):
        provider = _make_provider()
        info = await provider.get_info("sb-user1")
        assert info is not None
        assert info.id == "sb-user1"
        assert info.status == "running"

    @pytest.mark.asyncio
    async def test_get_info_not_found(self):
        client = _mock_client()
        client.get_sprite = AsyncMock(side_effect=SpritesAPIError(404, "not found"))
        provider = SpritesProvider(client=client)
        info = await provider.get_info("sb-missing")
        assert info is None

    @pytest.mark.asyncio
    async def test_get_info_api_error_propagates(self):
        client = _mock_client()
        client.get_sprite = AsyncMock(side_effect=SpritesAPIError(500, "error"))
        provider = SpritesProvider(client=client)
        with pytest.raises(SpritesAPIError):
            await provider.get_info("sb-user1")


# ─────────────────────── health_check ───────────────────────


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy(self):
        client = _mock_client()
        client.exec = AsyncMock(return_value=(0, '{"status":"ok"}', ""))
        provider = SpritesProvider(client=client)
        assert await provider.health_check("sb-user1") is True

    @pytest.mark.asyncio
    async def test_unhealthy(self):
        client = _mock_client()
        client.exec = AsyncMock(side_effect=SpritesExecError(1, "", "connection refused"))
        provider = SpritesProvider(client=client)
        assert await provider.health_check("sb-user1") is False

    @pytest.mark.asyncio
    async def test_timeout_returns_false(self):
        client = _mock_client()
        client.exec = AsyncMock(side_effect=TimeoutError())
        provider = SpritesProvider(client=client)
        assert await provider.health_check("sb-user1") is False


# ─────────────────────── get_logs ───────────────────────


class TestGetLogs:
    @pytest.mark.asyncio
    async def test_get_logs(self):
        client = _mock_client()
        client.exec = AsyncMock(return_value=(0, "line1\nline2\nline3\n", ""))
        provider = SpritesProvider(client=client)
        logs = await provider.get_logs("sb-user1", limit=50)
        assert logs == ["line1", "line2", "line3"]

    @pytest.mark.asyncio
    async def test_get_logs_failure(self):
        client = _mock_client()
        client.exec = AsyncMock(side_effect=SpritesExecError(1, "", ""))
        provider = SpritesProvider(client=client)
        logs = await provider.get_logs("sb-user1")
        assert logs == []


# ─────────────────────── stream_logs ───────────────────────


class TestStreamLogs:
    @pytest.mark.asyncio
    async def test_stream_logs(self):
        client = _mock_client()
        client.exec = AsyncMock(return_value=(0, "line1\nline2\n", ""))
        provider = SpritesProvider(client=client)
        lines = []
        async for line in provider.stream_logs("sb-user1"):
            lines.append(line)
        assert lines == ["line1", "line2"]

    @pytest.mark.asyncio
    async def test_stream_logs_error(self):
        client = _mock_client()
        client.exec = AsyncMock(side_effect=SpritesExecError(1, "", ""))
        provider = SpritesProvider(client=client)
        lines = []
        async for line in provider.stream_logs("sb-user1"):
            lines.append(line)
        assert "(log streaming unavailable)" in lines[0]


# ─────────────────────── Checkpoints ───────────────────────


class TestCheckpoints:
    def test_supports_checkpoints(self):
        provider = _make_provider()
        assert provider.supports_checkpoints() is True

    @pytest.mark.asyncio
    async def test_create_checkpoint(self):
        provider = _make_provider()
        result = await provider.create_checkpoint("sb-user1", label="before refactor")
        assert result.success
        assert result.data.id == "chk-1"

    @pytest.mark.asyncio
    async def test_create_checkpoint_failure(self):
        client = _mock_client()
        client.create_checkpoint = AsyncMock(
            side_effect=SpritesAPIError(500, "error")
        )
        provider = SpritesProvider(client=client)
        result = await provider.create_checkpoint("sb-user1")
        assert not result.success
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        provider = _make_provider()
        result = await provider.list_checkpoints("sb-user1")
        assert result.success
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_list_checkpoints_failure(self):
        client = _mock_client()
        client.list_checkpoints = AsyncMock(
            side_effect=SpritesAPIError(500, "error")
        )
        provider = SpritesProvider(client=client)
        result = await provider.list_checkpoints("sb-user1")
        assert not result.success

    @pytest.mark.asyncio
    async def test_restore_checkpoint(self):
        provider = _make_provider()
        result = await provider.restore_checkpoint("sb-user1", "chk-1")
        assert result.success

    @pytest.mark.asyncio
    async def test_restore_checkpoint_failure(self):
        client = _mock_client()
        client.restore_checkpoint = AsyncMock(
            side_effect=SpritesAPIError(404, "not found")
        )
        provider = SpritesProvider(client=client)
        result = await provider.restore_checkpoint("sb-user1", "chk-bad")
        assert not result.success


# ─────────────────────── update_credentials ───────────────────────


class TestUpdateCredentials:
    @pytest.mark.asyncio
    async def test_update_api_key(self):
        client = _mock_client()
        provider = SpritesProvider(client=client)
        result = await provider.update_credentials("sb-user1", anthropic_api_key="new-key")
        assert result is True
        client.exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_oauth(self):
        client = _mock_client()
        provider = SpritesProvider(client=client)
        result = await provider.update_credentials("sb-user1", oauth_token="new-tok")
        assert result is True

    @pytest.mark.asyncio
    async def test_update_no_credentials(self):
        provider = _make_provider()
        result = await provider.update_credentials("sb-user1")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_failure(self):
        client = _mock_client()
        client.exec = AsyncMock(side_effect=SpritesExecError(1, "", "permission denied"))
        provider = SpritesProvider(client=client)
        result = await provider.update_credentials("sb-user1", anthropic_api_key="key")
        assert result is False


# ─────────────────────── Status mapping ───────────────────────


class TestStatusMapping:
    @pytest.mark.parametrize("sprites_status,expected", [
        ("running", "running"),
        ("sleeping", "sleeping"),
        ("starting", "starting"),
        ("creating", "creating"),
        ("stopping", "stopping"),
        ("stopped", "stopped"),
        ("error", "error"),
        ("unknown", "error"),
    ])
    def test_status_mapping(self, sprites_status, expected):
        provider = _make_provider()
        assert provider._sprite_status_to_sandbox(sprites_status) == expected
