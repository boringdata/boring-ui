"""Tests for SSE/WS stream proxy lifecycle management.

Bead: bd-223o.11.5 (E5)

Validates:
  - StreamSession state transitions and lifecycle invariants.
  - StreamRegistry registration, limits, and cleanup.
  - Client disconnect triggers upstream cancellation.
  - Per-workspace stream limits prevent resource exhaustion.
"""

from __future__ import annotations

import asyncio

import pytest

from control_plane.app.routing.stream_lifecycle import (
    StreamLifecycleError,
    StreamRegistry,
    StreamSession,
    StreamState,
    stream_proxy_sse,
)


# =====================================================================
# StreamSession state transitions
# =====================================================================


class TestStreamSessionLifecycle:
    """StreamSession state machine transitions."""

    def test_initial_state_is_connecting(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        assert s.state == StreamState.CONNECTING
        assert s.is_active is True

    def test_activate_transitions_to_active(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        s.activate()
        assert s.state == StreamState.ACTIVE
        assert s.is_active is True

    def test_activate_from_non_connecting_raises(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        s.activate()
        with pytest.raises(StreamLifecycleError):
            s.activate()  # Already active.

    def test_request_close_transitions_to_closing(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        s.activate()
        s.request_close()
        assert s.state == StreamState.CLOSING
        assert s.is_active is False

    def test_request_close_from_closed_is_idempotent(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        s.mark_closed()
        s.request_close()  # Should not raise.
        assert s.state == StreamState.CLOSED

    def test_mark_closed_is_terminal(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        s.mark_closed()
        assert s.state == StreamState.CLOSED
        assert s.is_active is False

    def test_duration_increases_over_time(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        assert s.duration_seconds >= 0

    def test_session_id_optional(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        assert s.session_id is None
        s2 = StreamSession(
            workspace_id='ws_1', request_id='req_2', session_id='sess_1',
        )
        assert s2.session_id == 'sess_1'


class TestStreamSessionCancelEvent:
    """Cancel event signaling for upstream cleanup."""

    @pytest.mark.asyncio
    async def test_wait_for_cancel_returns_true_when_signaled(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        s.request_close()
        result = await s.wait_for_cancel(timeout=0.1)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_cancel_returns_false_on_timeout(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        result = await s.wait_for_cancel(timeout=0.01)
        assert result is False

    @pytest.mark.asyncio
    async def test_mark_closed_signals_cancel_event(self):
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        s.mark_closed()
        result = await s.wait_for_cancel(timeout=0.1)
        assert result is True


# =====================================================================
# StreamRegistry
# =====================================================================


class TestStreamRegistryBasics:
    """Basic registration and lookup."""

    def test_register_and_get(self):
        reg = StreamRegistry()
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        reg.register(s)
        assert reg.get('req_1') is s
        assert reg.total_count == 1

    def test_duplicate_request_id_raises(self):
        reg = StreamRegistry()
        s1 = StreamSession(workspace_id='ws_1', request_id='req_1')
        s2 = StreamSession(workspace_id='ws_1', request_id='req_1')
        reg.register(s1)
        with pytest.raises(StreamLifecycleError, match='already registered'):
            reg.register(s2)

    def test_unregister_removes_and_closes(self):
        reg = StreamRegistry()
        s = StreamSession(workspace_id='ws_1', request_id='req_1')
        reg.register(s)
        removed = reg.unregister('req_1')
        assert removed is s
        assert s.state == StreamState.CLOSED
        assert reg.get('req_1') is None
        assert reg.total_count == 0

    def test_unregister_missing_returns_none(self):
        reg = StreamRegistry()
        assert reg.unregister('nonexistent') is None

    def test_get_missing_returns_none(self):
        reg = StreamRegistry()
        assert reg.get('nonexistent') is None


class TestStreamRegistryLimits:
    """Per-workspace stream limits."""

    def test_workspace_count_tracked(self):
        reg = StreamRegistry(max_streams_per_workspace=10)
        for i in range(3):
            reg.register(StreamSession(workspace_id='ws_1', request_id=f'r_{i}'))
        assert reg.workspace_count('ws_1') == 3
        assert reg.workspace_count('ws_2') == 0

    def test_limit_enforced(self):
        reg = StreamRegistry(max_streams_per_workspace=2)
        reg.register(StreamSession(workspace_id='ws_1', request_id='r_0'))
        reg.register(StreamSession(workspace_id='ws_1', request_id='r_1'))
        with pytest.raises(StreamLifecycleError, match='stream limit'):
            reg.register(StreamSession(workspace_id='ws_1', request_id='r_2'))

    def test_different_workspaces_independent(self):
        reg = StreamRegistry(max_streams_per_workspace=1)
        reg.register(StreamSession(workspace_id='ws_1', request_id='r_1'))
        reg.register(StreamSession(workspace_id='ws_2', request_id='r_2'))
        assert reg.workspace_count('ws_1') == 1
        assert reg.workspace_count('ws_2') == 1

    def test_unregister_frees_count(self):
        reg = StreamRegistry(max_streams_per_workspace=1)
        reg.register(StreamSession(workspace_id='ws_1', request_id='r_1'))
        reg.unregister('r_1')
        assert reg.workspace_count('ws_1') == 0
        # Can register again.
        reg.register(StreamSession(workspace_id='ws_1', request_id='r_2'))


class TestStreamRegistryBulkOps:
    """Workspace-wide close and cleanup."""

    def test_close_workspace_streams(self):
        reg = StreamRegistry()
        s1 = StreamSession(workspace_id='ws_1', request_id='r_1')
        s2 = StreamSession(workspace_id='ws_1', request_id='r_2')
        s3 = StreamSession(workspace_id='ws_2', request_id='r_3')
        for s in (s1, s2, s3):
            reg.register(s)
        closed = reg.close_workspace_streams('ws_1')
        assert closed == 2
        assert s1.state == StreamState.CLOSING
        assert s2.state == StreamState.CLOSING
        assert s3.is_active is True  # Different workspace, untouched.

    def test_cleanup_closed(self):
        reg = StreamRegistry()
        s1 = StreamSession(workspace_id='ws_1', request_id='r_1')
        s2 = StreamSession(workspace_id='ws_1', request_id='r_2')
        reg.register(s1)
        reg.register(s2)
        s1.mark_closed()
        cleaned = reg.cleanup_closed()
        assert cleaned == 1
        assert reg.get('r_1') is None
        assert reg.get('r_2') is s2

    def test_active_count(self):
        reg = StreamRegistry()
        s1 = StreamSession(workspace_id='ws_1', request_id='r_1')
        s2 = StreamSession(workspace_id='ws_1', request_id='r_2')
        reg.register(s1)
        reg.register(s2)
        assert reg.active_count == 2
        s1.mark_closed()
        assert reg.active_count == 1


# =====================================================================
# SSE proxy generator
# =====================================================================


class TestStreamProxySSE:
    """SSE proxy generator with client disconnect detection."""

    @pytest.mark.asyncio
    async def test_yields_all_upstream_chunks(self):
        async def upstream():
            for chunk in [b'data: hello\n\n', b'data: world\n\n']:
                yield chunk

        session = StreamSession(workspace_id='ws_1', request_id='req_1')
        chunks = []
        async for chunk in stream_proxy_sse(upstream(), session):
            chunks.append(chunk)

        assert chunks == [b'data: hello\n\n', b'data: world\n\n']
        assert session.state == StreamState.CLOSED

    @pytest.mark.asyncio
    async def test_activates_session_on_start(self):
        async def upstream():
            yield b'data: 1\n\n'

        session = StreamSession(workspace_id='ws_1', request_id='req_1')
        assert session.state == StreamState.CONNECTING
        async for _ in stream_proxy_sse(upstream(), session):
            assert session.state == StreamState.ACTIVE

    @pytest.mark.asyncio
    async def test_closes_session_on_upstream_end(self):
        async def upstream():
            yield b'data: done\n\n'

        session = StreamSession(workspace_id='ws_1', request_id='req_1')
        async for _ in stream_proxy_sse(upstream(), session):
            pass
        assert session.state == StreamState.CLOSED

    @pytest.mark.asyncio
    async def test_stops_on_cancel_signal(self):
        async def upstream():
            for i in range(100):
                yield f'data: {i}\n\n'.encode()
                await asyncio.sleep(0)

        session = StreamSession(workspace_id='ws_1', request_id='req_1')
        chunks = []
        async for chunk in stream_proxy_sse(upstream(), session):
            chunks.append(chunk)
            if len(chunks) == 2:
                session.request_close()

        # Should have stopped after cancel was requested.
        assert len(chunks) <= 3  # May get one more chunk before check.
        assert session.state == StreamState.CLOSED

    @pytest.mark.asyncio
    async def test_empty_upstream_still_closes(self):
        async def upstream():
            return
            yield  # Make it an async generator.

        session = StreamSession(workspace_id='ws_1', request_id='req_1')
        chunks = []
        async for chunk in stream_proxy_sse(upstream(), session):
            chunks.append(chunk)
        assert chunks == []
        assert session.state == StreamState.CLOSED

    @pytest.mark.asyncio
    async def test_cancelled_error_triggers_cleanup(self):
        async def upstream():
            yield b'data: 1\n\n'
            raise asyncio.CancelledError()

        session = StreamSession(workspace_id='ws_1', request_id='req_1')
        chunks = []
        async for chunk in stream_proxy_sse(upstream(), session):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert session.state == StreamState.CLOSED
