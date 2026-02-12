"""Unit tests for PTY WebSocket bridge."""
import json
import time

import pytest

from boring_ui.api.pty_bridge import (
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_HEARTBEAT_TIMEOUT,
    DEFAULT_HISTORY_BUFFER_SIZE,
    PTYBridge,
    PTYBridgeConfig,
    PTYSessionState,
)


class TestPTYBridgeConfig:

    def test_defaults(self):
        cfg = PTYBridgeConfig()
        assert cfg.heartbeat_interval == DEFAULT_HEARTBEAT_INTERVAL
        assert cfg.heartbeat_timeout == DEFAULT_HEARTBEAT_TIMEOUT
        assert cfg.history_buffer_size == DEFAULT_HISTORY_BUFFER_SIZE

    def test_custom(self):
        cfg = PTYBridgeConfig(heartbeat_interval=10, heartbeat_timeout=5, history_buffer_size=1024)
        assert cfg.heartbeat_interval == 10
        assert cfg.heartbeat_timeout == 5
        assert cfg.history_buffer_size == 1024


class TestPTYSessionState:

    def test_fields(self):
        s = PTYSessionState(session_id='s1', exec_session_id='e1', template_id='shell')
        assert s.session_id == 's1'
        assert s.exec_session_id == 'e1'
        assert s.template_id == 'shell'
        assert s.closed is False
        assert s.exit_code is None
        assert s.history_buffer == ''

    def test_append_output(self):
        s = PTYSessionState(session_id='s1', exec_session_id='e1', template_id='t')
        s.append_output('hello', 1024)
        assert s.history_buffer == 'hello'

    def test_append_output_trims(self):
        s = PTYSessionState(session_id='s1', exec_session_id='e1', template_id='t')
        s.append_output('abcde', 3)
        assert s.history_buffer == 'cde'
        assert len(s.history_buffer) == 3

    def test_append_output_updates_activity(self):
        s = PTYSessionState(session_id='s1', exec_session_id='e1', template_id='t')
        before = s.last_activity
        time.sleep(0.01)
        s.append_output('x', 1024)
        assert s.last_activity >= before

    def test_touch(self):
        s = PTYSessionState(session_id='s1', exec_session_id='e1', template_id='t')
        before = s.last_activity
        time.sleep(0.01)
        s.touch()
        assert s.last_activity >= before


class TestPTYBridgeSessionManagement:

    def test_create_session(self):
        bridge = PTYBridge()
        state = bridge.create_session('s1', 'e1', 'shell')
        assert state.session_id == 's1'
        assert state.exec_session_id == 'e1'
        assert state.template_id == 'shell'

    def test_get_session(self):
        bridge = PTYBridge()
        bridge.create_session('s1', 'e1', 'shell')
        assert bridge.get_session('s1') is not None
        assert bridge.get_session('s1').session_id == 's1'

    def test_get_session_missing(self):
        bridge = PTYBridge()
        assert bridge.get_session('nope') is None

    def test_remove_session(self):
        bridge = PTYBridge()
        state = bridge.create_session('s1', 'e1', 'shell')
        bridge.remove_session('s1')
        assert bridge.get_session('s1') is None
        assert state.closed is True

    def test_remove_missing_is_noop(self):
        bridge = PTYBridge()
        bridge.remove_session('nope')  # Should not raise

    def test_session_count(self):
        bridge = PTYBridge()
        assert bridge.session_count == 0
        bridge.create_session('s1', 'e1', 't')
        assert bridge.session_count == 1
        bridge.create_session('s2', 'e2', 't')
        assert bridge.session_count == 2

    def test_active_sessions(self):
        bridge = PTYBridge()
        bridge.create_session('s1', 'e1', 't')
        s2 = bridge.create_session('s2', 'e2', 't')
        s2.closed = True
        active = bridge.active_sessions
        assert len(active) == 1
        assert active[0].session_id == 's1'


class TestParseInbound:

    def test_valid_json_with_type(self):
        bridge = PTYBridge()
        msg = bridge.parse_inbound('{"type": "input", "data": "ls\\n"}')
        assert msg['type'] == 'input'
        assert msg['data'] == 'ls\n'

    def test_valid_json_no_type(self):
        bridge = PTYBridge()
        msg = bridge.parse_inbound('{"data": "hello"}')
        assert msg['type'] == 'input'
        assert msg['data'] == '{"data": "hello"}'

    def test_not_dict(self):
        bridge = PTYBridge()
        msg = bridge.parse_inbound('[1, 2, 3]')
        assert msg['type'] == 'input'

    def test_invalid_json(self):
        bridge = PTYBridge()
        msg = bridge.parse_inbound('raw text')
        assert msg['type'] == 'input'
        assert msg['data'] == 'raw text'

    def test_resize_message(self):
        bridge = PTYBridge()
        msg = bridge.parse_inbound('{"type": "resize", "rows": 40, "cols": 120}')
        assert msg['type'] == 'resize'
        assert msg['rows'] == 40
        assert msg['cols'] == 120

    def test_ping_message(self):
        bridge = PTYBridge()
        msg = bridge.parse_inbound('{"type": "ping"}')
        assert msg['type'] == 'ping'


class TestHandlers:

    def setup_method(self):
        self.bridge = PTYBridge()
        self.session = self.bridge.create_session('s1', 'e1', 'shell')

    def test_handle_input(self):
        result = self.bridge.handle_input(self.session, 'ls\n')
        assert result == {'action': 'write', 'data': 'ls\n'}

    def test_handle_resize(self):
        result = self.bridge.handle_resize(self.session, 40, 120)
        assert result == {'action': 'resize', 'rows': 40, 'cols': 120}

    def test_handle_resize_clamps_low(self):
        result = self.bridge.handle_resize(self.session, 0, -5)
        assert result['rows'] == 1
        assert result['cols'] == 1

    def test_handle_resize_clamps_high(self):
        result = self.bridge.handle_resize(self.session, 9999, 9999)
        assert result['rows'] == 500
        assert result['cols'] == 500

    def test_handle_ping(self):
        result = self.bridge.handle_ping(self.session)
        assert result == {'action': 'send', 'message': {'type': 'pong'}}

    def test_handle_output(self):
        result = self.bridge.handle_output(self.session, 'hello world')
        assert result == {'action': 'send', 'message': {'type': 'output', 'data': 'hello world'}}
        assert self.session.history_buffer == 'hello world'

    def test_handle_exit(self):
        result = self.bridge.handle_exit(self.session, 0)
        assert result == {'action': 'send', 'message': {'type': 'exit', 'code': 0}}
        assert self.session.closed is True
        assert self.session.exit_code == 0

    def test_handle_exit_nonzero(self):
        result = self.bridge.handle_exit(self.session, 137)
        assert result['message']['code'] == 137


class TestRouteInbound:

    def setup_method(self):
        self.bridge = PTYBridge()
        self.session = self.bridge.create_session('s1', 'e1', 'shell')

    def test_route_input(self):
        result = self.bridge.route_inbound(self.session, {'type': 'input', 'data': 'ls'})
        assert result['action'] == 'write'

    def test_route_resize(self):
        result = self.bridge.route_inbound(self.session, {'type': 'resize', 'rows': 30, 'cols': 80})
        assert result['action'] == 'resize'

    def test_route_ping(self):
        result = self.bridge.route_inbound(self.session, {'type': 'ping'})
        assert result['action'] == 'send'

    def test_route_unknown(self):
        result = self.bridge.route_inbound(self.session, {'type': 'foobar'})
        assert result == {'action': 'noop'}

    def test_route_default_type(self):
        result = self.bridge.route_inbound(self.session, {})
        assert result['action'] == 'write'

    def test_route_input_default_data(self):
        result = self.bridge.route_inbound(self.session, {'type': 'input'})
        assert result == {'action': 'write', 'data': ''}

    def test_route_resize_defaults(self):
        result = self.bridge.route_inbound(self.session, {'type': 'resize'})
        assert result == {'action': 'resize', 'rows': 24, 'cols': 80}


class TestMessageBuilders:

    def setup_method(self):
        self.bridge = PTYBridge()

    def test_build_history_message(self):
        session = self.bridge.create_session('s1', 'e1', 't')
        session.history_buffer = 'previous output'
        msg = self.bridge.build_history_message(session)
        assert msg == {'type': 'history', 'data': 'previous output'}

    def test_build_history_empty(self):
        session = self.bridge.create_session('s1', 'e1', 't')
        assert self.bridge.build_history_message(session) is None

    def test_build_error_message(self):
        msg = self.bridge.build_error_message('something went wrong')
        assert msg == {'type': 'error', 'message': 'something went wrong'}

    def test_build_session_not_found(self):
        msg = self.bridge.build_session_not_found()
        assert msg == {'type': 'session_not_found'}


class TestCloseCodeMapping:

    def test_session_not_found(self):
        bridge = PTYBridge()
        code = bridge.close_code_for_error('session_not_found')
        assert code == 4001

    def test_session_terminated(self):
        bridge = PTYBridge()
        code = bridge.close_code_for_error('session_terminated')
        assert code == 4002

    def test_close_reason(self):
        bridge = PTYBridge()
        reason = bridge.close_reason_for_error('session_not_found')
        assert isinstance(reason, str)
        assert len(reason) > 0

    def test_unknown_error_key(self):
        bridge = PTYBridge()
        code = bridge.close_code_for_error('totally_unknown')
        assert code == 1011  # WS_INTERNAL_ERROR
