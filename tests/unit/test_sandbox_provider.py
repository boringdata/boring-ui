"""Tests for SandboxProvider interface extensions.

Covers SandboxStatus, SandboxCreateConfig, SandboxInfo extensions,
checkpoint defaults, and update_credentials default.
"""
import asyncio
from datetime import datetime

import pytest

from boring_ui.api.modules.sandbox.provider import (
    CheckpointInfo,
    CheckpointResult,
    SandboxCreateConfig,
    SandboxInfo,
    SandboxProvider,
    SandboxStatus,
)


# ─────────────────────── SandboxStatus ───────────────────────


class TestSandboxStatus:
    def test_all_states_exist(self):
        expected = {
            "creating", "starting", "running", "sleeping",
            "waking", "stopping", "stopped", "error",
        }
        actual = {s.value for s in SandboxStatus}
        assert actual == expected

    def test_string_comparison(self):
        assert SandboxStatus.running == "running"
        assert SandboxStatus.sleeping == "sleeping"

    def test_from_string(self):
        assert SandboxStatus("running") == SandboxStatus.running


# ─────────────────────── SandboxCreateConfig ───────────────────────


class TestSandboxCreateConfig:
    def test_defaults(self):
        cfg = SandboxCreateConfig()
        assert cfg.user_id == ""
        assert cfg.repo_url == ""
        assert cfg.branch == "main"
        assert cfg.agent == "claude"
        assert cfg.setup_timeout == 300.0
        assert cfg.health_timeout == 30.0

    def test_sanitizes_repo_url(self):
        cfg = SandboxCreateConfig(repo_url="https://github.com/org/repo.git")
        assert cfg.repo_url == "https://github.com/org/repo.git"

    def test_rejects_bad_repo_url(self):
        with pytest.raises(ValueError):
            SandboxCreateConfig(repo_url="ftp://evil.com/repo")

    def test_rejects_bad_branch(self):
        with pytest.raises(ValueError):
            SandboxCreateConfig(branch="main..develop")

    def test_sanitizes_branch_whitespace(self):
        cfg = SandboxCreateConfig(branch="  feature/x  ")
        assert cfg.branch == "feature/x"

    def test_empty_repo_url_ok(self):
        cfg = SandboxCreateConfig(repo_url="")
        assert cfg.repo_url == ""

    def test_validate_credentials_both_fails(self):
        cfg = SandboxCreateConfig(
            anthropic_api_key="key", oauth_token="tok"
        )
        with pytest.raises(ValueError, match="not both"):
            cfg.validate_credentials()

    def test_validate_credentials_require_none_fails(self):
        cfg = SandboxCreateConfig()
        with pytest.raises(ValueError, match="At least one"):
            cfg.validate_credentials(require=True)

    def test_validate_credentials_key_only(self):
        cfg = SandboxCreateConfig(anthropic_api_key="key")
        cfg.validate_credentials(require=True)  # no raise

    def test_validate_credentials_oauth_only(self):
        cfg = SandboxCreateConfig(oauth_token="tok")
        cfg.validate_credentials(require=True)  # no raise

    def test_validate_credentials_none_ok_when_not_required(self):
        cfg = SandboxCreateConfig()
        cfg.validate_credentials(require=False)  # no raise


# ─────────────────────── SandboxInfo ───────────────────────


class TestSandboxInfo:
    def test_backward_compat(self):
        """Existing code that passes only the 5 original fields still works."""
        info = SandboxInfo(
            id="sb-1",
            base_url="http://127.0.0.1:2468",
            status="running",
            workspace_path="/tmp/ws",
            provider="local",
        )
        assert info.protocol == "rest+sse"
        assert info.user_id == ""
        assert info.repo_url == ""

    def test_new_fields(self):
        info = SandboxInfo(
            id="sb-2",
            base_url="https://abc.sprites.app",
            status="running",
            workspace_path="/home/sprite/workspace",
            provider="sprites",
            protocol="rest+sse",
            user_id="user-42",
            repo_url="https://github.com/org/repo.git",
        )
        assert info.protocol == "rest+sse"
        assert info.user_id == "user-42"
        assert info.repo_url == "https://github.com/org/repo.git"


# ─────────────────────── CheckpointInfo ───────────────────────


class TestCheckpointInfo:
    def test_minimal(self):
        cp = CheckpointInfo(id="chk-1")
        assert cp.id == "chk-1"
        assert cp.label == ""
        assert cp.created_at is None
        assert cp.size_bytes is None

    def test_full(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        cp = CheckpointInfo(
            id="chk-2", label="before refactor", created_at=now, size_bytes=1024
        )
        assert cp.label == "before refactor"
        assert cp.created_at == now
        assert cp.size_bytes == 1024


# ─────────────────────── CheckpointResult ───────────────────────


class TestCheckpointResult:
    def test_success(self):
        r = CheckpointResult(success=True, data=CheckpointInfo(id="c1"))
        assert r.success
        assert r.data.id == "c1"
        assert r.error is None

    def test_failure(self):
        r = CheckpointResult(success=False, error="Not supported")
        assert not r.success
        assert r.data is None
        assert r.error == "Not supported"

    def test_generic_list(self):
        r: CheckpointResult[list[CheckpointInfo]] = CheckpointResult(
            success=True,
            data=[CheckpointInfo(id="a"), CheckpointInfo(id="b")],
        )
        assert len(r.data) == 2


# ─────────────────────── Provider defaults ───────────────────────


class _MinimalProvider(SandboxProvider):
    """Concrete provider with only the required abstract methods."""

    async def create(self, sandbox_id, config):
        return SandboxInfo(
            id=sandbox_id, base_url="", status="running",
            workspace_path="", provider="test",
        )

    async def destroy(self, sandbox_id):
        pass

    async def get_info(self, sandbox_id):
        return None

    async def get_logs(self, sandbox_id, limit=100):
        return []

    async def stream_logs(self, sandbox_id):
        yield ""

    async def health_check(self, sandbox_id):
        return True


class TestProviderDefaults:
    @pytest.fixture
    def provider(self):
        return _MinimalProvider()

    def test_supports_checkpoints_default(self, provider):
        assert provider.supports_checkpoints() is False

    @pytest.mark.asyncio
    async def test_create_checkpoint_default(self, provider):
        r = await provider.create_checkpoint("sb-1", label="test")
        assert not r.success
        assert r.error == "Not supported"

    @pytest.mark.asyncio
    async def test_restore_checkpoint_default(self, provider):
        r = await provider.restore_checkpoint("sb-1", "chk-1")
        assert not r.success
        assert r.error == "Not supported"

    @pytest.mark.asyncio
    async def test_list_checkpoints_default(self, provider):
        r = await provider.list_checkpoints("sb-1")
        assert not r.success
        assert r.error == "Not supported"

    @pytest.mark.asyncio
    async def test_update_credentials_default(self, provider):
        result = await provider.update_credentials(
            "sb-1", anthropic_api_key="new-key"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_update_credentials_no_args(self, provider):
        result = await provider.update_credentials("sb-1")
        assert result is False
