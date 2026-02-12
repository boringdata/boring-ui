"""Chat WebSocket bridge for sandbox mode.

Bridges the /ws/claude-stream WebSocket to a Sprites exec session,
preserving local-mode frame semantics:

  Inbound (browser -> bridge):
    - user: {type: "user", message: "..."} -> write to exec
    - control: {type: "control", ...} -> forward to exec
    - control_response: {type: "control_response", ...} -> forward to exec
    - command: {type: "command", ...} -> forward to exec
    - ping: {type: "ping"} -> respond with pong
    - interrupt: {type: "interrupt"} -> signal exec
    - restart: {type: "restart"} -> terminate + respawn

  Outbound (bridge -> browser):
    - system: {type: "system", subtype: "connected|error|interrupted|restarted"}
    - assistant: {type: "assistant", ...} from exec stdout
    - control_request: {type: "control_request", ...} from exec
    - pong: {type: "pong"} in response to ping
    - error: {type: "error", message: "..."} on failure

Features:
  - Heartbeat/keepalive with configurable interval and timeout
  - system.connected payload with session_id, resumed flag, settings
  - Message history buffer for reconnection replay
  - Session token authorization via opaque tokens
  - Connection parameter validation (session_id, mode, model, etc.)
  - Normalized close codes for frontend consistency
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

from .error_normalization import (
    WS_PROVIDER_UNAVAILABLE,
    WS_SESSION_NOT_FOUND,
    WS_SESSION_TERMINATED,
    WS_VALIDATION_ERROR,
    normalize_ws_error,
)

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_INTERVAL = 30.0
DEFAULT_HEARTBEAT_TIMEOUT = 10.0
DEFAULT_HISTORY_LINES = 500
DEFAULT_IDLE_TTL = 60.0
DEFAULT_MAX_SESSIONS = 10

VALID_MODES = frozenset({'ask', 'act', 'plan'})
VALID_INBOUND_TYPES = frozenset({
    'user', 'control', 'control_response', 'command',
    'ping', 'interrupt', 'restart',
})


@dataclass
class ChatBridgeConfig:
    """Configuration for the Chat WebSocket bridge."""
    heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL
    heartbeat_timeout: float = DEFAULT_HEARTBEAT_TIMEOUT
    history_lines: int = DEFAULT_HISTORY_LINES
    idle_ttl: float = DEFAULT_IDLE_TTL
    max_sessions: int = DEFAULT_MAX_SESSIONS


@dataclass
class ChatConnectionParams:
    """Validated connection parameters from WebSocket query string."""
    session_id: str
    resume: bool = False
    force_new: bool = False
    mode: str = 'ask'
    model: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)
    max_thinking_tokens: int | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None

    @property
    def settings(self) -> dict:
        """Build settings dict for system.connected payload."""
        s: dict = {'mode': self.mode}
        if self.model:
            s['model'] = self.model
        if self.max_thinking_tokens is not None:
            s['max_thinking_tokens'] = self.max_thinking_tokens
        return s


@dataclass
class ChatSessionState:
    """State for a single bridged chat session."""
    session_id: str
    exec_session_id: str
    template_id: str
    params: ChatConnectionParams
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    history: deque = field(default_factory=lambda: deque(maxlen=DEFAULT_HISTORY_LINES))
    client_count: int = 0
    closed: bool = False
    exit_code: int | None = None

    def append_message(self, msg: dict) -> None:
        """Append an outbound message to history."""
        self.history.append(msg)
        self.last_activity = time.time()

    def touch(self) -> None:
        self.last_activity = time.time()

    @property
    def is_idle(self) -> bool:
        return self.client_count == 0 and not self.closed

    @property
    def idle_duration(self) -> float:
        if not self.is_idle:
            return 0.0
        return time.time() - self.last_activity


class ChatBridge:
    """Manages Chat WebSocket bridging to exec sessions in sandbox mode.

    Handles message routing, heartbeat, history buffering, connection
    parameter validation, and session token authorization.
    """

    def __init__(
        self,
        config: ChatBridgeConfig | None = None,
    ) -> None:
        self._config = config or ChatBridgeConfig()
        self._sessions: dict[str, ChatSessionState] = {}

    def validate_session_id(self, raw: str | None) -> str:
        """Validate or generate a session UUID.

        Returns a valid UUID string. Generates one if input is None or invalid.
        """
        if raw is None:
            return str(uuid.uuid4())
        try:
            uuid.UUID(raw)
            return raw
        except (ValueError, AttributeError):
            logger.warning('Invalid session_id %r, generating new UUID', raw)
            return str(uuid.uuid4())

    def parse_connection_params(self, query: dict[str, str]) -> ChatConnectionParams:
        """Parse and validate WebSocket connection query parameters.

        Args:
            query: Dict of query string key-value pairs.

        Returns:
            Validated ChatConnectionParams.

        Raises:
            ValueError: If mode is invalid.
        """
        session_id = self.validate_session_id(query.get('session_id'))
        resume = query.get('resume', '0') == '1'
        force_new = query.get('force_new', '0') == '1'
        mode = query.get('mode', 'ask')

        if mode not in VALID_MODES:
            raise ValueError(f'Invalid mode: {mode!r}. Must be one of {sorted(VALID_MODES)}')

        model = query.get('model') or None

        allowed_tools = []
        if query.get('allowed_tools'):
            allowed_tools = [t.strip() for t in query['allowed_tools'].split(',') if t.strip()]

        disallowed_tools = []
        if query.get('disallowed_tools'):
            disallowed_tools = [t.strip() for t in query['disallowed_tools'].split(',') if t.strip()]

        max_thinking_tokens = None
        if query.get('max_thinking_tokens'):
            try:
                max_thinking_tokens = int(query['max_thinking_tokens'])
            except ValueError:
                pass

        max_turns = None
        if query.get('max_turns'):
            try:
                max_turns = int(query['max_turns'])
            except ValueError:
                pass

        max_budget_usd = None
        if query.get('max_budget_usd'):
            try:
                max_budget_usd = float(query['max_budget_usd'])
            except ValueError:
                pass

        return ChatConnectionParams(
            session_id=session_id,
            resume=resume,
            force_new=force_new,
            mode=mode,
            model=model,
            allowed_tools=allowed_tools,
            disallowed_tools=disallowed_tools,
            max_thinking_tokens=max_thinking_tokens,
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
        )

    def create_session(
        self,
        session_id: str,
        exec_session_id: str,
        template_id: str,
        params: ChatConnectionParams,
    ) -> ChatSessionState:
        """Register a new bridged chat session."""
        state = ChatSessionState(
            session_id=session_id,
            exec_session_id=exec_session_id,
            template_id=template_id,
            params=params,
            history=deque(maxlen=self._config.history_lines),
        )
        self._sessions[session_id] = state
        return state

    def get_session(self, session_id: str) -> ChatSessionState | None:
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            session.closed = True

    def add_client(self, session: ChatSessionState) -> None:
        """Track a new WebSocket client attaching to a session."""
        session.client_count += 1
        session.touch()

    def remove_client(self, session: ChatSessionState) -> None:
        """Track a WebSocket client detaching from a session."""
        session.client_count = max(0, session.client_count - 1)
        session.touch()

    def find_evictable_session(self) -> ChatSessionState | None:
        """Find the oldest idle session for eviction.

        Returns None if no idle sessions exist.
        """
        idle = [s for s in self._sessions.values() if s.is_idle]
        if not idle:
            return None
        return min(idle, key=lambda s: s.last_activity)

    def should_evict(self) -> bool:
        """Check if session count has reached max and eviction is needed."""
        return len(self._sessions) >= self._config.max_sessions

    def parse_inbound(self, raw: str) -> dict:
        """Parse an inbound WebSocket message.

        Returns a dict with at least 'type' key.
        Raw text without JSON is treated as a user message.
        """
        try:
            msg = json.loads(raw)
            if not isinstance(msg, dict) or 'type' not in msg:
                return {'type': 'user', 'message': raw}
            return msg
        except (json.JSONDecodeError, ValueError):
            return {'type': 'user', 'message': raw}

    def handle_user(self, session: ChatSessionState, message: str) -> dict:
        """Process a user chat message.

        Returns:
          {'action': 'write', 'data': {...}} -> write to exec stdin
        """
        session.touch()
        return {
            'action': 'write',
            'data': {'type': 'user', 'message': message},
        }

    def handle_control(self, session: ChatSessionState, msg: dict) -> dict:
        """Process a control message.

        Returns:
          {'action': 'write', 'data': {...}} -> forward to exec
        """
        session.touch()
        return {'action': 'write', 'data': msg}

    def handle_control_response(self, session: ChatSessionState, msg: dict) -> dict:
        """Process a control_response message.

        Returns:
          {'action': 'write', 'data': {...}} -> forward to exec
        """
        session.touch()
        return {'action': 'write', 'data': msg}

    def handle_command(self, session: ChatSessionState, msg: dict) -> dict:
        """Process a command message.

        Returns:
          {'action': 'write', 'data': {...}} -> forward to exec
        """
        session.touch()
        return {'action': 'write', 'data': msg}

    def handle_ping(self, session: ChatSessionState) -> dict:
        """Process a ping message.

        Returns:
          {'action': 'send', 'message': {'type': 'pong'}}
        """
        session.touch()
        return {'action': 'send', 'message': {'type': 'pong'}}

    def handle_interrupt(self, session: ChatSessionState) -> dict:
        """Process an interrupt request.

        Returns:
          {'action': 'interrupt'}
        """
        session.touch()
        return {'action': 'interrupt'}

    def handle_restart(self, session: ChatSessionState) -> dict:
        """Process a restart request.

        Returns:
          {'action': 'restart'}
        """
        session.touch()
        return {'action': 'restart'}

    def handle_output(self, session: ChatSessionState, msg: dict) -> dict:
        """Process output from exec stdout.

        Buffers for history and returns message to broadcast.
        """
        session.append_message(msg)
        return {'action': 'broadcast', 'message': msg}

    def handle_exit(self, session: ChatSessionState, exit_code: int) -> dict:
        """Process exec session exit."""
        session.exit_code = exit_code
        session.closed = True
        return {
            'action': 'broadcast',
            'message': {
                'type': 'system',
                'subtype': 'terminated',
                'exit_code': exit_code,
            },
        }

    def build_connected_message(
        self, session: ChatSessionState, resumed: bool = False,
    ) -> dict:
        """Build the system.connected payload sent on WebSocket accept."""
        return {
            'type': 'system',
            'subtype': 'connected',
            'session_id': session.session_id,
            'resumed': resumed,
            'settings': session.params.settings,
        }

    def build_history_messages(self, session: ChatSessionState) -> list[dict]:
        """Build history replay messages for reconnection.

        Returns a list of messages (may be empty).
        """
        return list(session.history)

    def build_error_message(self, message: str) -> dict:
        """Build a safe error message for the browser."""
        return {'type': 'system', 'subtype': 'error', 'message': message}

    def build_session_not_found(self) -> dict:
        """Build a session_not_found message."""
        return {'type': 'system', 'subtype': 'error', 'message': 'Session not found'}

    def build_interrupted_message(self) -> dict:
        """Build the system.interrupted message."""
        return {'type': 'system', 'subtype': 'interrupted'}

    def build_restarted_message(self, session: ChatSessionState) -> dict:
        """Build the system.restarted message."""
        return {
            'type': 'system',
            'subtype': 'restarted',
            'session_id': session.session_id,
            'settings': session.params.settings,
        }

    def route_inbound(self, session: ChatSessionState, msg: dict) -> dict:
        """Route a parsed inbound message to the appropriate handler.

        Returns an action dict.
        """
        msg_type = msg.get('type', 'user')

        if msg_type == 'user':
            return self.handle_user(session, msg.get('message', ''))
        elif msg_type == 'control':
            return self.handle_control(session, msg)
        elif msg_type == 'control_response':
            return self.handle_control_response(session, msg)
        elif msg_type == 'command':
            return self.handle_command(session, msg)
        elif msg_type == 'ping':
            return self.handle_ping(session)
        elif msg_type == 'interrupt':
            return self.handle_interrupt(session)
        elif msg_type == 'restart':
            return self.handle_restart(session)
        else:
            return {'action': 'noop'}

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def active_sessions(self) -> list[ChatSessionState]:
        return [s for s in self._sessions.values() if not s.closed]

    @property
    def idle_sessions(self) -> list[ChatSessionState]:
        return [s for s in self._sessions.values() if s.is_idle]

    def close_code_for_error(self, error_key: str) -> int:
        """Map an error key to a WebSocket close code."""
        norm = normalize_ws_error(error_key)
        return norm.ws_close_code

    def close_reason_for_error(self, error_key: str) -> str:
        """Map an error key to a WebSocket close reason."""
        norm = normalize_ws_error(error_key)
        return norm.message
