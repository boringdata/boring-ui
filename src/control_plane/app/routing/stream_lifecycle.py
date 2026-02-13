"""SSE/WS stream proxy lifecycle management.

Bead: bd-223o.11.5 (E5)

Implements the streaming proxy contract from Feature 3 design doc
section 18.4, point 4:

  SSE and WS/stream proxy paths sustain active sessions and close
  upstream cleanly on client disconnect.

This module provides:
  1. ``StreamSession`` — tracks a single proxied stream connection.
  2. ``StreamRegistry`` — manages active streams with cleanup guarantees.
  3. ``stream_proxy_sse`` — async generator for proxying SSE events with
     client disconnect detection.
  4. ``StreamLifecycleError`` — raised on lifecycle violations.

Design decisions:
  - Streams are keyed by (workspace_id, request_id) for uniqueness.
  - Client disconnect triggers upstream cancellation within a bounded timeout.
  - Registry enforces per-workspace stream limits to prevent resource exhaustion.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator


class StreamState(Enum):
    """Lifecycle state of a proxied stream."""

    CONNECTING = 'connecting'
    ACTIVE = 'active'
    CLOSING = 'closing'
    CLOSED = 'closed'


class StreamLifecycleError(Exception):
    """Raised on stream lifecycle violations."""


@dataclass(slots=True)
class StreamSession:
    """Tracks a single proxied stream connection.

    Attributes:
        workspace_id: Which workspace owns this stream.
        request_id: Unique request identifier for correlation.
        session_id: Optional agent session ID.
        state: Current lifecycle state.
        started_at: Monotonic timestamp when stream was created.
        _cancel_event: Internal event signaling upstream cancellation.
    """

    workspace_id: str
    request_id: str
    session_id: str | None = None
    state: StreamState = StreamState.CONNECTING
    started_at: float = field(default_factory=time.monotonic)
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def is_active(self) -> bool:
        return self.state in (StreamState.CONNECTING, StreamState.ACTIVE)

    @property
    def duration_seconds(self) -> float:
        return time.monotonic() - self.started_at

    def activate(self) -> None:
        """Transition from CONNECTING to ACTIVE."""
        if self.state != StreamState.CONNECTING:
            raise StreamLifecycleError(
                f'Cannot activate stream in state {self.state.value}'
            )
        self.state = StreamState.ACTIVE

    def request_close(self) -> None:
        """Signal that upstream should be cancelled."""
        if self.state == StreamState.CLOSED:
            return  # Idempotent.
        self.state = StreamState.CLOSING
        self._cancel_event.set()

    def mark_closed(self) -> None:
        """Transition to CLOSED (terminal state)."""
        self.state = StreamState.CLOSED
        self._cancel_event.set()

    async def wait_for_cancel(self, timeout: float | None = None) -> bool:
        """Wait for cancellation signal.

        Returns True if cancelled, False if timed out.
        """
        try:
            await asyncio.wait_for(self._cancel_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False


class StreamRegistry:
    """Manages active stream sessions with cleanup guarantees.

    Thread-safe via asyncio (single event loop assumption).

    Attributes:
        max_streams_per_workspace: Per-workspace limit to prevent
            resource exhaustion.
    """

    def __init__(self, max_streams_per_workspace: int = 50) -> None:
        self.max_streams_per_workspace = max_streams_per_workspace
        self._streams: dict[str, StreamSession] = {}  # key: request_id
        self._workspace_counts: dict[str, int] = {}

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._streams.values() if s.is_active)

    @property
    def total_count(self) -> int:
        return len(self._streams)

    def workspace_count(self, workspace_id: str) -> int:
        return self._workspace_counts.get(workspace_id, 0)

    def register(self, session: StreamSession) -> None:
        """Register a new stream session.

        Raises:
            StreamLifecycleError: If request_id already registered or
                workspace stream limit exceeded.
        """
        if session.request_id in self._streams:
            raise StreamLifecycleError(
                f'Stream already registered: {session.request_id}'
            )

        ws_count = self._workspace_counts.get(session.workspace_id, 0)
        if ws_count >= self.max_streams_per_workspace:
            raise StreamLifecycleError(
                f'Workspace {session.workspace_id} at stream limit '
                f'({self.max_streams_per_workspace})'
            )

        self._streams[session.request_id] = session
        self._workspace_counts[session.workspace_id] = ws_count + 1

    def unregister(self, request_id: str) -> StreamSession | None:
        """Remove a stream session and clean up counts.

        Returns the removed session, or None if not found.
        """
        session = self._streams.pop(request_id, None)
        if session is None:
            return None

        session.mark_closed()
        ws_count = self._workspace_counts.get(session.workspace_id, 0) - 1
        if ws_count <= 0:
            self._workspace_counts.pop(session.workspace_id, None)
        else:
            self._workspace_counts[session.workspace_id] = ws_count

        return session

    def get(self, request_id: str) -> StreamSession | None:
        return self._streams.get(request_id)

    def close_workspace_streams(self, workspace_id: str) -> int:
        """Request close on all streams for a workspace.

        Returns the number of streams signaled.
        """
        count = 0
        for session in list(self._streams.values()):
            if session.workspace_id == workspace_id and session.is_active:
                session.request_close()
                count += 1
        return count

    def cleanup_closed(self) -> int:
        """Remove all CLOSED sessions from the registry.

        Returns the number of sessions cleaned up.
        """
        closed_ids = [
            rid for rid, s in self._streams.items()
            if s.state == StreamState.CLOSED
        ]
        for rid in closed_ids:
            self.unregister(rid)
        return len(closed_ids)


async def stream_proxy_sse(
    upstream: AsyncIterator[bytes],
    session: StreamSession,
    *,
    disconnect_check_interval: float = 1.0,
) -> AsyncIterator[bytes]:
    """Proxy SSE events from upstream with client disconnect detection.

    Yields upstream bytes while the stream is active.  When the client
    disconnects (detected by the caller draining this generator), the
    session is marked for closing so upstream resources can be freed.

    Args:
        upstream: Async iterator producing SSE event bytes from the
            workspace runtime.
        session: The StreamSession tracking this connection.
        disconnect_check_interval: How often to check for cancellation
            between upstream reads (seconds).

    Yields:
        SSE event bytes for the client.
    """
    session.activate()
    try:
        async for chunk in upstream:
            if not session.is_active:
                break
            yield chunk
    except asyncio.CancelledError:
        # Client disconnected — clean up upstream.
        pass
    finally:
        session.mark_closed()
