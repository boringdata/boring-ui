"""PTY WebSocket bridge for sandbox mode.

Bridges the /ws/pty WebSocket to a Sprites exec session, preserving
local-mode frame semantics:

  Inbound (browser -> bridge):
    - input: {type: "input", data: "..."} -> write to exec
    - resize: {type: "resize", rows: N, cols: N} -> resize exec
    - ping: {type: "ping"} -> respond with pong

  Outbound (bridge -> browser):
    - output: {type: "output", data: "..."} from exec stdout
    - pong: {type: "pong"} in response to ping
    - history: {type: "history", data: "..."} on reconnect
    - error: {type: "error", message: "..."} on failure
    - exit: {type: "exit", code: N} when exec terminates
    - session_not_found: {type: "session_not_found"} if session gone

Features:
  - Heartbeat/keepalive with configurable interval and timeout
  - Immediate resize forwarding
  - Normalized close codes for frontend consistency
  - Session token validation for attach authorization
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field

from .error_normalization import (
    WS_PROVIDER_UNAVAILABLE,
    WS_SESSION_NOT_FOUND,
    WS_SESSION_TERMINATED,
    WS_VALIDATION_ERROR,
    normalize_ws_error,
)
from .session_tokens import (
    SessionTokenError,
    issue_session_token,
    validate_session_token,
)

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_INTERVAL = 30.0
DEFAULT_HEARTBEAT_TIMEOUT = 10.0
DEFAULT_HISTORY_BUFFER_SIZE = 200 * 1024  # 200 KB


@dataclass
class PTYBridgeConfig:
    """Configuration for the PTY WebSocket bridge."""
    heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL
    heartbeat_timeout: float = DEFAULT_HEARTBEAT_TIMEOUT
    history_buffer_size: int = DEFAULT_HISTORY_BUFFER_SIZE


@dataclass
class PTYSessionState:
    """State for a single bridged PTY session."""
    session_id: str
    exec_session_id: str
    template_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    history_buffer: str = ''
    closed: bool = False
    exit_code: int | None = None

    def append_output(self, data: str, max_size: int) -> None:
        """Append output to history buffer, trimming to max_size."""
        self.history_buffer += data
        if len(self.history_buffer) > max_size:
            self.history_buffer = self.history_buffer[-max_size:]
        self.last_activity = time.time()

    def touch(self) -> None:
        self.last_activity = time.time()


class PTYBridge:
    """Manages PTY WebSocket bridging to exec sessions in sandbox mode.

    Handles message routing, heartbeat, history buffering, and
    session token authorization.
    """

    def __init__(
        self,
        config: PTYBridgeConfig | None = None,
    ) -> None:
        self._config = config or PTYBridgeConfig()
        self._sessions: dict[str, PTYSessionState] = {}

    def create_session(
        self,
        session_id: str,
        exec_session_id: str,
        template_id: str,
    ) -> PTYSessionState:
        """Register a new bridged PTY session."""
        state = PTYSessionState(
            session_id=session_id,
            exec_session_id=exec_session_id,
            template_id=template_id,
        )
        self._sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> PTYSessionState | None:
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            session.closed = True

    def parse_inbound(self, raw: str) -> dict:
        """Parse an inbound WebSocket message.

        Returns a dict with at least 'type' key.
        Raw text without JSON is treated as input.
        """
        try:
            msg = json.loads(raw)
            if not isinstance(msg, dict) or 'type' not in msg:
                return {'type': 'input', 'data': raw}
            return msg
        except (json.JSONDecodeError, ValueError):
            return {'type': 'input', 'data': raw}

    def handle_input(self, session: PTYSessionState, data: str) -> dict:
        """Process an input message.

        Returns an action dict for the caller to execute:
          {'action': 'write', 'data': '...'} -> write to exec stdin
        """
        session.touch()
        return {'action': 'write', 'data': data}

    def handle_resize(
        self, session: PTYSessionState, rows: int, cols: int,
    ) -> dict:
        """Process a resize message.

        Returns:
          {'action': 'resize', 'rows': N, 'cols': N}
        """
        session.touch()
        # Clamp to reasonable values
        rows = max(1, min(rows, 500))
        cols = max(1, min(cols, 500))
        return {'action': 'resize', 'rows': rows, 'cols': cols}

    def handle_ping(self, session: PTYSessionState) -> dict:
        """Process a ping message.

        Returns:
          {'action': 'send', 'message': {'type': 'pong'}}
        """
        session.touch()
        return {'action': 'send', 'message': {'type': 'pong'}}

    def handle_output(self, session: PTYSessionState, data: str) -> dict:
        """Process output from exec stdout.

        Buffers for history and returns message to send.
        """
        session.append_output(data, self._config.history_buffer_size)
        return {'action': 'send', 'message': {'type': 'output', 'data': data}}

    def handle_exit(self, session: PTYSessionState, exit_code: int) -> dict:
        """Process exec session exit."""
        session.exit_code = exit_code
        session.closed = True
        return {'action': 'send', 'message': {'type': 'exit', 'code': exit_code}}

    def build_history_message(self, session: PTYSessionState) -> dict | None:
        """Build a history replay message for reconnection.

        Returns None if no history available.
        """
        if session.history_buffer:
            return {'type': 'history', 'data': session.history_buffer}
        return None

    def build_error_message(self, message: str) -> dict:
        """Build a safe error message for the browser."""
        return {'type': 'error', 'message': message}

    def build_session_not_found(self) -> dict:
        """Build a session_not_found message."""
        return {'type': 'session_not_found'}

    def route_inbound(self, session: PTYSessionState, msg: dict) -> dict:
        """Route a parsed inbound message to the appropriate handler.

        Returns an action dict.
        """
        msg_type = msg.get('type', 'input')

        if msg_type == 'input':
            return self.handle_input(session, msg.get('data', ''))
        elif msg_type == 'resize':
            rows = msg.get('rows', 24)
            cols = msg.get('cols', 80)
            return self.handle_resize(session, rows, cols)
        elif msg_type == 'ping':
            return self.handle_ping(session)
        else:
            # Unknown message type - treat as no-op
            return {'action': 'noop'}

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def active_sessions(self) -> list[PTYSessionState]:
        return [s for s in self._sessions.values() if not s.closed]

    def close_code_for_error(self, error_key: str) -> int:
        """Map an error key to a WebSocket close code."""
        norm = normalize_ws_error(error_key)
        return norm.ws_close_code

    def close_reason_for_error(self, error_key: str) -> str:
        """Map an error key to a WebSocket close reason."""
        norm = normalize_ws_error(error_key)
        return norm.message
