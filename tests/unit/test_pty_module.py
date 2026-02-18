"""Unit tests for boring_ui.api.modules.pty module."""
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from boring_ui.api.modules.pty.service import (
    PTYSession,
    SharedSession,
    PTYService,
    get_session_registry,
    PTY_HISTORY_BYTES,
    PTY_IDLE_TTL,
    PTY_MAX_SESSIONS,
)


class TestPTYSessionBasic:
    """Tests for PTYSession class without actual process spawning."""

    def test_initial_state(self):
        """Test PTYSession initial state."""
        session = PTYSession()
        assert session.process is None
        assert session._read_task is None
        assert session._output_callback is None

    def test_exit_code_no_process(self):
        """Test exit_code returns None when no process."""
        session = PTYSession()
        assert session.exit_code is None

    def test_write_no_process(self):
        """Test write does nothing when no process."""
        session = PTYSession()
        # Should not raise
        session.write('test')

    def test_resize_no_process(self):
        """Test resize does nothing when no process."""
        session = PTYSession()
        # Should not raise
        session.resize(24, 80)

    def test_kill_no_process(self):
        """Test kill does nothing when no process."""
        session = PTYSession()
        # Should not raise
        session.kill()
        assert session.process is None


class TestPTYSessionWithMockedProcess:
    """Tests for PTYSession with mocked ptyprocess."""

    def test_write_with_alive_process(self):
        """Test write calls process.write when alive."""
        session = PTYSession()
        mock_process = MagicMock()
        mock_process.isalive.return_value = True
        session.process = mock_process

        session.write('test input')

        mock_process.write.assert_called_once_with('test input')

    def test_write_with_dead_process(self):
        """Test write does nothing when process is dead."""
        session = PTYSession()
        mock_process = MagicMock()
        mock_process.isalive.return_value = False
        session.process = mock_process

        session.write('test input')

        mock_process.write.assert_not_called()

    def test_resize_with_alive_process(self):
        """Test resize calls process.setwinsize when alive."""
        session = PTYSession()
        mock_process = MagicMock()
        mock_process.isalive.return_value = True
        session.process = mock_process

        session.resize(40, 120)

        mock_process.setwinsize.assert_called_once_with(40, 120)

    def test_resize_with_dead_process(self):
        """Test resize does nothing when process is dead."""
        session = PTYSession()
        mock_process = MagicMock()
        mock_process.isalive.return_value = False
        session.process = mock_process

        session.resize(40, 120)

        mock_process.setwinsize.assert_not_called()

    def test_kill_terminates_process(self):
        """Test kill terminates alive process."""
        session = PTYSession()
        mock_process = MagicMock()
        mock_process.isalive.return_value = True
        session.process = mock_process

        session.kill()

        mock_process.terminate.assert_called_once_with(force=True)
        assert session.process is None

    def test_exit_code_with_terminated_process(self):
        """Test exit_code returns exitstatus when terminated."""
        session = PTYSession()
        mock_process = MagicMock()
        mock_process.isalive.return_value = False
        mock_process.exitstatus = 42
        session.process = mock_process

        assert session.exit_code == 42

    def test_exit_code_with_alive_process(self):
        """Test exit_code returns None when process is alive."""
        session = PTYSession()
        mock_process = MagicMock()
        mock_process.isalive.return_value = True
        session.process = mock_process

        assert session.exit_code is None


class TestSharedSession:
    """Tests for SharedSession class."""

    def test_initial_state(self):
        """Test SharedSession initial state."""
        session = SharedSession(
            session_id='test-123',
            command=['bash'],
            cwd=Path('/tmp'),
        )
        assert session.session_id == 'test-123'
        assert session.command == ['bash']
        assert session.cwd == Path('/tmp')
        assert len(session.clients) == 0
        assert len(session.history) == 0
        assert session._started is False

    def test_is_alive_no_process(self):
        """Test is_alive returns False when no process."""
        session = SharedSession(
            session_id='test-123',
            command=['bash'],
            cwd=Path('/tmp'),
        )
        assert session.is_alive() is False

    def test_is_alive_with_alive_process(self):
        """Test is_alive returns True when process is alive."""
        session = SharedSession(
            session_id='test-123',
            command=['bash'],
            cwd=Path('/tmp'),
        )
        mock_process = MagicMock()
        mock_process.isalive.return_value = True
        session.pty.process = mock_process

        assert session.is_alive() is True

    def test_is_alive_with_dead_process(self):
        """Test is_alive returns False when process is dead."""
        session = SharedSession(
            session_id='test-123',
            command=['bash'],
            cwd=Path('/tmp'),
        )
        mock_process = MagicMock()
        mock_process.isalive.return_value = False
        session.pty.process = mock_process

        assert session.is_alive() is False

    def test_idle_seconds(self):
        """Test idle_seconds calculation."""
        session = SharedSession(
            session_id='test-123',
            command=['bash'],
            cwd=Path('/tmp'),
        )
        # Set last_activity to 10 seconds ago
        session.last_activity = datetime.now(timezone.utc) - timedelta(seconds=10)

        idle = session.idle_seconds
        assert 9 <= idle <= 11  # Allow some tolerance

    def test_write_updates_activity(self):
        """Test write updates last_activity."""
        session = SharedSession(
            session_id='test-123',
            command=['bash'],
            cwd=Path('/tmp'),
        )
        old_activity = session.last_activity - timedelta(seconds=10)
        session.last_activity = old_activity

        # Mock the PTY to avoid actual process interaction
        session.pty.process = MagicMock()
        session.pty.process.isalive.return_value = True

        session.write('test')

        assert session.last_activity > old_activity

    @pytest.mark.asyncio
    async def test_remove_client(self):
        """Test remove_client removes from set."""
        session = SharedSession(
            session_id='test-123',
            command=['bash'],
            cwd=Path('/tmp'),
        )
        mock_ws = MagicMock()
        session.clients.add(mock_ws)
        assert len(session.clients) == 1

        await session.remove_client(mock_ws)

        assert len(session.clients) == 0

    def test_kill_cancels_read_task(self):
        """Test kill cancels read task and kills PTY."""
        session = SharedSession(
            session_id='test-123',
            command=['bash'],
            cwd=Path('/tmp'),
        )
        mock_task = MagicMock()
        session._read_task = mock_task
        mock_process = MagicMock()
        mock_process.isalive.return_value = True
        session.pty.process = mock_process

        session.kill()

        mock_task.cancel.assert_called_once()
        mock_process.terminate.assert_called_once()


class TestPTYService:
    """Tests for PTYService class."""

    def test_initial_state(self):
        """Test PTYService initial state."""
        service = PTYService()
        assert len(service.registry) == 0
        assert service._cleanup_task is None

    @pytest.mark.asyncio
    async def test_get_or_create_session_creates_new(self):
        """Test get_or_create_session creates new session."""
        service = PTYService()

        session, is_new = await service.get_or_create_session(
            session_id=None,
            command=['bash'],
            cwd=Path('/tmp'),
        )

        assert is_new is True
        assert session.command == ['bash']
        assert len(service.registry) == 1

    @pytest.mark.asyncio
    async def test_get_or_create_session_returns_existing(self):
        """Test get_or_create_session returns existing session."""
        service = PTYService()

        session1, is_new1 = await service.get_or_create_session(
            session_id=None,
            command=['bash'],
            cwd=Path('/tmp'),
        )
        assert is_new1 is True
        session_id = session1.session_id

        session2, is_new2 = await service.get_or_create_session(
            session_id=session_id,
            command=['bash'],
            cwd=Path('/tmp'),
        )

        assert is_new2 is False
        assert session2 is session1
        assert len(service.registry) == 1

    @pytest.mark.asyncio
    async def test_get_or_create_session_max_sessions(self):
        """Test get_or_create_session raises when max reached."""
        service = PTYService()

        # Fill up to max sessions
        with patch('boring_ui.api.modules.pty.service.PTY_MAX_SESSIONS', 2):
            await service.get_or_create_session(None, ['bash'], Path('/tmp'))
            await service.get_or_create_session(None, ['bash'], Path('/tmp'))

            with pytest.raises(ValueError, match='Maximum sessions reached'):
                await service.get_or_create_session(None, ['bash'], Path('/tmp'))

    @pytest.mark.asyncio
    async def test_get_or_create_session_allows_reconnect_at_capacity(self):
        """Reconnect should work when the registry is at max sessions."""
        service = PTYService()

        with patch('boring_ui.api.modules.pty.service.PTY_MAX_SESSIONS', 1):
            existing, is_new = await service.get_or_create_session(None, ['bash'], Path('/tmp'))
            assert is_new is True

            session, is_new = await service.get_or_create_session(
                existing.session_id,
                ['bash'],
                Path('/tmp'),
            )

            assert is_new is False
            assert session is existing

    @pytest.mark.asyncio
    async def test_ensure_cleanup_running_starts_task(self):
        """Test ensure_cleanup_running starts cleanup task."""
        service = PTYService()
        assert service._cleanup_task is None

        await service.ensure_cleanup_running()

        assert service._cleanup_task is not None
        assert not service._cleanup_task.done()

        # Cancel for cleanup
        service._cleanup_task.cancel()
        try:
            await service._cleanup_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_ensure_cleanup_running_idempotent(self):
        """Test ensure_cleanup_running doesn't restart existing task."""
        service = PTYService()

        await service.ensure_cleanup_running()
        task1 = service._cleanup_task

        await service.ensure_cleanup_running()
        task2 = service._cleanup_task

        assert task1 is task2

        # Cancel for cleanup
        service._cleanup_task.cancel()
        try:
            await service._cleanup_task
        except asyncio.CancelledError:
            pass


class TestGetSessionRegistry:
    """Tests for get_session_registry function."""

    def test_returns_global_registry(self):
        """Test get_session_registry returns global registry."""
        registry = get_session_registry()
        assert isinstance(registry, dict)


class TestConfigurationConstants:
    """Tests for configuration constants."""

    def test_pty_history_bytes_default(self):
        """Test PTY_HISTORY_BYTES has sensible default."""
        assert PTY_HISTORY_BYTES > 0
        assert PTY_HISTORY_BYTES == 200000  # Default value

    def test_pty_idle_ttl_default(self):
        """Test PTY_IDLE_TTL has sensible default."""
        assert PTY_IDLE_TTL > 0
        assert PTY_IDLE_TTL == 30  # Default value

    def test_pty_max_sessions_default(self):
        """Test PTY_MAX_SESSIONS has sensible default."""
        assert PTY_MAX_SESSIONS > 0
        assert PTY_MAX_SESSIONS == 20  # Default value
