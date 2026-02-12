"""Unit tests for Chat WebSocket bridge."""
import time

import pytest

from boring_ui.api.chat_bridge import (
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_HEARTBEAT_TIMEOUT,
    DEFAULT_HISTORY_LINES,
    DEFAULT_IDLE_TTL,
    DEFAULT_MAX_SESSIONS,
    VALID_MODES,
    ChatBridge,
    ChatBridgeConfig,
    ChatConnectionParams,
    ChatSessionState,
)


class TestChatBridgeConfig:

    def test_defaults(self):
        cfg = ChatBridgeConfig()
        assert cfg.heartbeat_interval == DEFAULT_HEARTBEAT_INTERVAL
        assert cfg.heartbeat_timeout == DEFAULT_HEARTBEAT_TIMEOUT
        assert cfg.history_lines == DEFAULT_HISTORY_LINES
        assert cfg.idle_ttl == DEFAULT_IDLE_TTL
        assert cfg.max_sessions == DEFAULT_MAX_SESSIONS

    def test_custom(self):
        cfg = ChatBridgeConfig(
            heartbeat_interval=10, heartbeat_timeout=5,
            history_lines=100, idle_ttl=30, max_sessions=5,
        )
        assert cfg.heartbeat_interval == 10
        assert cfg.max_sessions == 5


class TestChatConnectionParams:

    def test_defaults(self):
        p = ChatConnectionParams(session_id='abc')
        assert p.session_id == 'abc'
        assert p.resume is False
        assert p.force_new is False
        assert p.mode == 'ask'
        assert p.model is None
        assert p.allowed_tools == []
        assert p.disallowed_tools == []
        assert p.max_thinking_tokens is None
        assert p.max_turns is None
        assert p.max_budget_usd is None

    def test_settings_minimal(self):
        p = ChatConnectionParams(session_id='abc', mode='act')
        s = p.settings
        assert s == {'mode': 'act'}

    def test_settings_full(self):
        p = ChatConnectionParams(
            session_id='abc', mode='plan', model='sonnet',
            max_thinking_tokens=1000,
        )
        s = p.settings
        assert s['mode'] == 'plan'
        assert s['model'] == 'sonnet'
        assert s['max_thinking_tokens'] == 1000


class TestChatSessionState:

    def test_fields(self):
        params = ChatConnectionParams(session_id='s1')
        s = ChatSessionState(
            session_id='s1', exec_session_id='e1',
            template_id='chat', params=params,
        )
        assert s.session_id == 's1'
        assert s.exec_session_id == 'e1'
        assert s.template_id == 'chat'
        assert s.closed is False
        assert s.exit_code is None
        assert s.client_count == 0

    def test_append_message(self):
        params = ChatConnectionParams(session_id='s1')
        s = ChatSessionState(
            session_id='s1', exec_session_id='e1',
            template_id='chat', params=params,
        )
        msg = {'type': 'assistant', 'text': 'hello'}
        s.append_message(msg)
        assert list(s.history) == [msg]

    def test_touch(self):
        params = ChatConnectionParams(session_id='s1')
        s = ChatSessionState(
            session_id='s1', exec_session_id='e1',
            template_id='chat', params=params,
        )
        before = s.last_activity
        time.sleep(0.01)
        s.touch()
        assert s.last_activity >= before

    def test_is_idle_no_clients(self):
        params = ChatConnectionParams(session_id='s1')
        s = ChatSessionState(
            session_id='s1', exec_session_id='e1',
            template_id='chat', params=params,
        )
        assert s.is_idle is True

    def test_is_idle_with_clients(self):
        params = ChatConnectionParams(session_id='s1')
        s = ChatSessionState(
            session_id='s1', exec_session_id='e1',
            template_id='chat', params=params,
        )
        s.client_count = 1
        assert s.is_idle is False

    def test_is_idle_when_closed(self):
        params = ChatConnectionParams(session_id='s1')
        s = ChatSessionState(
            session_id='s1', exec_session_id='e1',
            template_id='chat', params=params,
        )
        s.closed = True
        assert s.is_idle is False

    def test_idle_duration(self):
        params = ChatConnectionParams(session_id='s1')
        s = ChatSessionState(
            session_id='s1', exec_session_id='e1',
            template_id='chat', params=params,
        )
        s.last_activity = time.time() - 10.0
        assert s.idle_duration >= 9.0

    def test_idle_duration_not_idle(self):
        params = ChatConnectionParams(session_id='s1')
        s = ChatSessionState(
            session_id='s1', exec_session_id='e1',
            template_id='chat', params=params,
        )
        s.client_count = 1
        assert s.idle_duration == 0.0


class TestValidateSessionId:

    def test_valid_uuid(self):
        bridge = ChatBridge()
        sid = bridge.validate_session_id('550e8400-e29b-41d4-a716-446655440000')
        assert sid == '550e8400-e29b-41d4-a716-446655440000'

    def test_none_generates(self):
        bridge = ChatBridge()
        sid = bridge.validate_session_id(None)
        import uuid
        uuid.UUID(sid)  # Should not raise

    def test_invalid_generates(self):
        bridge = ChatBridge()
        sid = bridge.validate_session_id('not-a-uuid')
        import uuid
        uuid.UUID(sid)  # Should not raise
        assert sid != 'not-a-uuid'

    def test_empty_string_generates(self):
        bridge = ChatBridge()
        sid = bridge.validate_session_id('')
        import uuid
        uuid.UUID(sid)


class TestParseConnectionParams:

    def test_minimal(self):
        bridge = ChatBridge()
        params = bridge.parse_connection_params({})
        assert params.mode == 'ask'
        assert params.resume is False
        assert params.force_new is False
        assert params.model is None

    def test_full_params(self):
        bridge = ChatBridge()
        params = bridge.parse_connection_params({
            'session_id': '550e8400-e29b-41d4-a716-446655440000',
            'resume': '1',
            'force_new': '0',
            'mode': 'act',
            'model': 'sonnet',
            'allowed_tools': 'read,write',
            'disallowed_tools': 'bash',
            'max_thinking_tokens': '1000',
            'max_turns': '10',
            'max_budget_usd': '5.0',
        })
        assert params.session_id == '550e8400-e29b-41d4-a716-446655440000'
        assert params.resume is True
        assert params.force_new is False
        assert params.mode == 'act'
        assert params.model == 'sonnet'
        assert params.allowed_tools == ['read', 'write']
        assert params.disallowed_tools == ['bash']
        assert params.max_thinking_tokens == 1000
        assert params.max_turns == 10
        assert params.max_budget_usd == 5.0

    def test_invalid_mode_raises(self):
        bridge = ChatBridge()
        with pytest.raises(ValueError, match='Invalid mode'):
            bridge.parse_connection_params({'mode': 'invalid'})

    def test_empty_model_is_none(self):
        bridge = ChatBridge()
        params = bridge.parse_connection_params({'model': ''})
        assert params.model is None

    def test_invalid_int_ignored(self):
        bridge = ChatBridge()
        params = bridge.parse_connection_params({
            'max_thinking_tokens': 'not_int',
            'max_turns': 'nope',
        })
        assert params.max_thinking_tokens is None
        assert params.max_turns is None

    def test_invalid_float_ignored(self):
        bridge = ChatBridge()
        params = bridge.parse_connection_params({'max_budget_usd': 'nope'})
        assert params.max_budget_usd is None

    def test_csv_tools_with_spaces(self):
        bridge = ChatBridge()
        params = bridge.parse_connection_params({
            'allowed_tools': ' read , write , bash ',
        })
        assert params.allowed_tools == ['read', 'write', 'bash']


class TestSessionManagement:

    def _make_params(self, **kw):
        return ChatConnectionParams(session_id='s1', **kw)

    def test_create_session(self):
        bridge = ChatBridge()
        params = self._make_params()
        state = bridge.create_session('s1', 'e1', 'chat', params)
        assert state.session_id == 's1'
        assert state.exec_session_id == 'e1'

    def test_get_session(self):
        bridge = ChatBridge()
        bridge.create_session('s1', 'e1', 'chat', self._make_params())
        assert bridge.get_session('s1') is not None

    def test_get_session_missing(self):
        bridge = ChatBridge()
        assert bridge.get_session('nope') is None

    def test_remove_session(self):
        bridge = ChatBridge()
        state = bridge.create_session('s1', 'e1', 'chat', self._make_params())
        bridge.remove_session('s1')
        assert bridge.get_session('s1') is None
        assert state.closed is True

    def test_remove_missing_is_noop(self):
        bridge = ChatBridge()
        bridge.remove_session('nope')

    def test_session_count(self):
        bridge = ChatBridge()
        assert bridge.session_count == 0
        bridge.create_session('s1', 'e1', 'chat', self._make_params())
        assert bridge.session_count == 1

    def test_active_sessions(self):
        bridge = ChatBridge()
        bridge.create_session('s1', 'e1', 'chat', self._make_params())
        s2 = bridge.create_session('s2', 'e2', 'chat', self._make_params())
        s2.closed = True
        assert len(bridge.active_sessions) == 1

    def test_idle_sessions(self):
        bridge = ChatBridge()
        s1 = bridge.create_session('s1', 'e1', 'chat', self._make_params())
        s2 = bridge.create_session('s2', 'e2', 'chat', self._make_params())
        s2.client_count = 1
        idle = bridge.idle_sessions
        assert len(idle) == 1
        assert idle[0].session_id == 's1'


class TestClientTracking:

    def test_add_client(self):
        bridge = ChatBridge()
        params = ChatConnectionParams(session_id='s1')
        session = bridge.create_session('s1', 'e1', 'chat', params)
        bridge.add_client(session)
        assert session.client_count == 1

    def test_remove_client(self):
        bridge = ChatBridge()
        params = ChatConnectionParams(session_id='s1')
        session = bridge.create_session('s1', 'e1', 'chat', params)
        session.client_count = 2
        bridge.remove_client(session)
        assert session.client_count == 1

    def test_remove_client_floor_zero(self):
        bridge = ChatBridge()
        params = ChatConnectionParams(session_id='s1')
        session = bridge.create_session('s1', 'e1', 'chat', params)
        bridge.remove_client(session)
        assert session.client_count == 0


class TestEviction:

    def _make_params(self):
        return ChatConnectionParams(session_id='x')

    def test_find_evictable_returns_oldest_idle(self):
        bridge = ChatBridge()
        s1 = bridge.create_session('s1', 'e1', 'chat', self._make_params())
        s1.last_activity = time.time() - 100
        s2 = bridge.create_session('s2', 'e2', 'chat', self._make_params())
        s2.last_activity = time.time() - 50
        evictable = bridge.find_evictable_session()
        assert evictable.session_id == 's1'

    def test_find_evictable_skips_active(self):
        bridge = ChatBridge()
        s1 = bridge.create_session('s1', 'e1', 'chat', self._make_params())
        s1.client_count = 1
        s2 = bridge.create_session('s2', 'e2', 'chat', self._make_params())
        evictable = bridge.find_evictable_session()
        assert evictable.session_id == 's2'

    def test_find_evictable_none_available(self):
        bridge = ChatBridge()
        s1 = bridge.create_session('s1', 'e1', 'chat', self._make_params())
        s1.client_count = 1
        assert bridge.find_evictable_session() is None

    def test_should_evict(self):
        bridge = ChatBridge(ChatBridgeConfig(max_sessions=2))
        bridge.create_session('s1', 'e1', 'chat', self._make_params())
        assert not bridge.should_evict()
        bridge.create_session('s2', 'e2', 'chat', self._make_params())
        assert bridge.should_evict()


class TestParseInbound:

    def test_valid_json_with_type(self):
        bridge = ChatBridge()
        msg = bridge.parse_inbound('{"type": "user", "message": "hello"}')
        assert msg['type'] == 'user'
        assert msg['message'] == 'hello'

    def test_valid_json_no_type(self):
        bridge = ChatBridge()
        msg = bridge.parse_inbound('{"message": "hello"}')
        assert msg['type'] == 'user'
        assert msg['message'] == '{"message": "hello"}'

    def test_not_dict(self):
        bridge = ChatBridge()
        msg = bridge.parse_inbound('[1, 2]')
        assert msg['type'] == 'user'

    def test_raw_text(self):
        bridge = ChatBridge()
        msg = bridge.parse_inbound('just some text')
        assert msg['type'] == 'user'
        assert msg['message'] == 'just some text'

    def test_control_message(self):
        bridge = ChatBridge()
        msg = bridge.parse_inbound('{"type": "control", "action": "initialize"}')
        assert msg['type'] == 'control'

    def test_ping_message(self):
        bridge = ChatBridge()
        msg = bridge.parse_inbound('{"type": "ping"}')
        assert msg['type'] == 'ping'


class TestHandlers:

    def setup_method(self):
        self.bridge = ChatBridge()
        self.params = ChatConnectionParams(session_id='s1', mode='ask')
        self.session = self.bridge.create_session('s1', 'e1', 'chat', self.params)

    def test_handle_user(self):
        result = self.bridge.handle_user(self.session, 'hello')
        assert result['action'] == 'write'
        assert result['data'] == {'type': 'user', 'message': 'hello'}

    def test_handle_control(self):
        msg = {'type': 'control', 'action': 'initialize'}
        result = self.bridge.handle_control(self.session, msg)
        assert result['action'] == 'write'
        assert result['data'] is msg

    def test_handle_control_response(self):
        msg = {'type': 'control_response', 'behavior': 'allow'}
        result = self.bridge.handle_control_response(self.session, msg)
        assert result['action'] == 'write'
        assert result['data'] is msg

    def test_handle_command(self):
        msg = {'type': 'command', 'text': '/help'}
        result = self.bridge.handle_command(self.session, msg)
        assert result['action'] == 'write'
        assert result['data'] is msg

    def test_handle_ping(self):
        result = self.bridge.handle_ping(self.session)
        assert result == {'action': 'send', 'message': {'type': 'pong'}}

    def test_handle_interrupt(self):
        result = self.bridge.handle_interrupt(self.session)
        assert result == {'action': 'interrupt'}

    def test_handle_restart(self):
        result = self.bridge.handle_restart(self.session)
        assert result == {'action': 'restart'}

    def test_handle_output(self):
        msg = {'type': 'assistant', 'text': 'hi'}
        result = self.bridge.handle_output(self.session, msg)
        assert result == {'action': 'broadcast', 'message': msg}
        assert msg in self.session.history

    def test_handle_exit(self):
        result = self.bridge.handle_exit(self.session, 0)
        assert result['action'] == 'broadcast'
        assert result['message']['type'] == 'system'
        assert result['message']['subtype'] == 'terminated'
        assert result['message']['exit_code'] == 0
        assert self.session.closed is True
        assert self.session.exit_code == 0


class TestRouteInbound:

    def setup_method(self):
        self.bridge = ChatBridge()
        self.params = ChatConnectionParams(session_id='s1')
        self.session = self.bridge.create_session('s1', 'e1', 'chat', self.params)

    def test_route_user(self):
        result = self.bridge.route_inbound(self.session, {'type': 'user', 'message': 'hi'})
        assert result['action'] == 'write'

    def test_route_control(self):
        result = self.bridge.route_inbound(self.session, {'type': 'control', 'action': 'init'})
        assert result['action'] == 'write'

    def test_route_control_response(self):
        result = self.bridge.route_inbound(self.session, {'type': 'control_response'})
        assert result['action'] == 'write'

    def test_route_command(self):
        result = self.bridge.route_inbound(self.session, {'type': 'command', 'text': '/x'})
        assert result['action'] == 'write'

    def test_route_ping(self):
        result = self.bridge.route_inbound(self.session, {'type': 'ping'})
        assert result['action'] == 'send'

    def test_route_interrupt(self):
        result = self.bridge.route_inbound(self.session, {'type': 'interrupt'})
        assert result == {'action': 'interrupt'}

    def test_route_restart(self):
        result = self.bridge.route_inbound(self.session, {'type': 'restart'})
        assert result == {'action': 'restart'}

    def test_route_unknown(self):
        result = self.bridge.route_inbound(self.session, {'type': 'foobar'})
        assert result == {'action': 'noop'}

    def test_route_default_type(self):
        result = self.bridge.route_inbound(self.session, {})
        assert result['action'] == 'write'


class TestMessageBuilders:

    def setup_method(self):
        self.bridge = ChatBridge()
        self.params = ChatConnectionParams(session_id='s1', mode='ask', model='sonnet')
        self.session = self.bridge.create_session('s1', 'e1', 'chat', self.params)

    def test_build_connected_new(self):
        msg = self.bridge.build_connected_message(self.session, resumed=False)
        assert msg['type'] == 'system'
        assert msg['subtype'] == 'connected'
        assert msg['session_id'] == 's1'
        assert msg['resumed'] is False
        assert msg['settings']['mode'] == 'ask'
        assert msg['settings']['model'] == 'sonnet'

    def test_build_connected_resumed(self):
        msg = self.bridge.build_connected_message(self.session, resumed=True)
        assert msg['resumed'] is True

    def test_build_history_messages(self):
        self.session.append_message({'type': 'assistant', 'text': 'a'})
        self.session.append_message({'type': 'assistant', 'text': 'b'})
        history = self.bridge.build_history_messages(self.session)
        assert len(history) == 2
        assert history[0]['text'] == 'a'

    def test_build_history_empty(self):
        history = self.bridge.build_history_messages(self.session)
        assert history == []

    def test_build_error_message(self):
        msg = self.bridge.build_error_message('something failed')
        assert msg == {'type': 'system', 'subtype': 'error', 'message': 'something failed'}

    def test_build_session_not_found(self):
        msg = self.bridge.build_session_not_found()
        assert msg['type'] == 'system'
        assert msg['subtype'] == 'error'
        assert 'not found' in msg['message'].lower()

    def test_build_interrupted(self):
        msg = self.bridge.build_interrupted_message()
        assert msg == {'type': 'system', 'subtype': 'interrupted'}

    def test_build_restarted(self):
        msg = self.bridge.build_restarted_message(self.session)
        assert msg['type'] == 'system'
        assert msg['subtype'] == 'restarted'
        assert msg['session_id'] == 's1'
        assert 'mode' in msg['settings']


class TestCloseCodeMapping:

    def test_session_not_found(self):
        bridge = ChatBridge()
        assert bridge.close_code_for_error('session_not_found') == 4001

    def test_session_terminated(self):
        bridge = ChatBridge()
        assert bridge.close_code_for_error('session_terminated') == 4002

    def test_close_reason(self):
        bridge = ChatBridge()
        reason = bridge.close_reason_for_error('session_not_found')
        assert isinstance(reason, str)
        assert len(reason) > 0

    def test_unknown_defaults_to_internal(self):
        bridge = ChatBridge()
        assert bridge.close_code_for_error('unknown_thing') == 1011
