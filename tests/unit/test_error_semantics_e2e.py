"""E2E validation of HTTP/WS error semantics.

Verifies that:
  1. No internal service names, URLs, or stack traces reach the browser
  2. Every upstream failure maps to a known browser-visible error shape
  3. WebSocket close codes are standardized across providers
  4. Auth failures, not-found, timeout, and degraded upstream scenarios
     produce consistent error shapes for both HTTP and WS flows
"""
import json

import pytest

from boring_ui.api.error_normalization import (
    ErrorCategory,
    NormalizedError,
    WS_AUTH_REQUIRED,
    WS_INTERNAL_ERROR,
    WS_PROVIDER_TIMEOUT,
    WS_PROVIDER_UNAVAILABLE,
    WS_RATE_LIMITED,
    WS_SESSION_NOT_FOUND,
    WS_SESSION_TERMINATED,
    WS_VALIDATION_ERROR,
    error_response_body,
    normalize_http_error,
    normalize_http_status,
    normalize_ws_error,
)
from boring_ui.api.http_delegation import (
    DelegationResponse,
    map_upstream_status,
)
from boring_ui.api.pty_bridge import PTYBridge
from boring_ui.api.chat_bridge import ChatBridge


# ── Internal detail leak patterns ──

# Patterns that should NEVER appear in browser-facing messages
INTERNAL_LEAK_PATTERNS = [
    'localhost',
    '127.0.0.1',
    '192.168.',
    '10.0.',
    'httpx',
    'aiohttp',
    'requests.',
    'urllib',
    'traceback',
    'Traceback',
    'File "/',
    'line ',
    'ConnectionRefused',
    'ConnectError',
    'workspace:',
    'sprites:',
    ':9000',
    ':8080',
    ':3000',
    'ECONNREFUSED',
    'ETIMEDOUT',
    'socket.timeout',
    'grpc.',
    'dns.resolver',
]


def assert_no_leaks(message: str, context: str = '') -> None:
    """Assert that a browser-facing message contains no internal details."""
    for pattern in INTERNAL_LEAK_PATTERNS:
        assert pattern not in message, (
            f'Internal detail leaked in {context}: '
            f'found {pattern!r} in {message!r}'
        )


# ── HTTP error shape validation ──


class TestHttpErrorShapeConsistency:
    """Verify all HTTP errors produce consistent browser-safe shapes."""

    ERROR_KEYS = [
        'bad_request', 'not_found', 'conflict', 'validation_error',
        'unauthorized', 'rate_limited', 'provider_error',
        'provider_unavailable', 'provider_timeout', 'transport_error',
        'internal_error',
    ]

    @pytest.mark.parametrize('key', ERROR_KEYS)
    def test_error_has_required_fields(self, key):
        norm = normalize_http_error(key)
        assert isinstance(norm.category, ErrorCategory)
        assert isinstance(norm.http_status, int)
        assert isinstance(norm.message, str)
        assert len(norm.message) > 0

    @pytest.mark.parametrize('key', ERROR_KEYS)
    def test_error_body_shape(self, key):
        norm = normalize_http_error(key)
        body = error_response_body(norm)
        assert 'error' in body
        assert 'category' in body
        assert isinstance(body['error'], str)
        assert isinstance(body['category'], str)

    @pytest.mark.parametrize('key', ERROR_KEYS)
    def test_no_internal_leaks_in_message(self, key):
        norm = normalize_http_error(
            key,
            internal_detail='httpx.ConnectError: Connection refused at 192.168.1.1:9000',
        )
        assert_no_leaks(norm.message, f'HTTP {key}')

    @pytest.mark.parametrize('key', ERROR_KEYS)
    def test_no_internal_leaks_in_body(self, key):
        norm = normalize_http_error(
            key,
            internal_detail='grpc.StatusCode.UNAVAILABLE: DNS resolution failed for sprites:9000',
        )
        body = error_response_body(norm)
        body_str = json.dumps(body)
        assert_no_leaks(body_str, f'HTTP body {key}')

    def test_unknown_key_safe(self):
        norm = normalize_http_error('totally_unknown_error')
        body = error_response_body(norm)
        assert body['category'] == 'internal'
        assert_no_leaks(body['error'], 'unknown HTTP key')

    @pytest.mark.parametrize('status', [400, 401, 403, 404, 409, 422, 429, 500, 502, 503, 504])
    def test_status_code_mapping_safe(self, status):
        norm = normalize_http_status(status)
        assert isinstance(norm.http_status, int)
        assert isinstance(norm.message, str)
        assert_no_leaks(norm.message, f'HTTP status {status}')


# ── WebSocket error shape validation ──


class TestWsErrorShapeConsistency:
    """Verify all WS errors produce consistent browser-safe shapes."""

    WS_KEYS = [
        'session_not_found', 'session_terminated', 'provider_unknown',
        'ws_validation_error', 'ws_rate_limited', 'ws_provider_unavailable',
        'ws_provider_timeout', 'ws_auth_required',
    ]

    @pytest.mark.parametrize('key', WS_KEYS)
    def test_ws_error_has_close_code(self, key):
        norm = normalize_ws_error(key)
        assert norm.ws_close_code > 0
        assert isinstance(norm.message, str)
        assert len(norm.message) > 0

    @pytest.mark.parametrize('key', WS_KEYS)
    def test_ws_close_code_in_valid_range(self, key):
        norm = normalize_ws_error(key)
        # Standard codes: 1000-1015
        # Application codes: 4000-4999
        assert (1000 <= norm.ws_close_code <= 1015) or (4000 <= norm.ws_close_code <= 4999)

    @pytest.mark.parametrize('key', WS_KEYS)
    def test_no_internal_leaks_in_ws_message(self, key):
        norm = normalize_ws_error(
            key,
            internal_detail='Connection to workspace:9000 refused via httpx',
        )
        assert_no_leaks(norm.message, f'WS {key}')

    def test_unknown_ws_key_safe(self):
        norm = normalize_ws_error('totally_unknown_ws_error')
        assert norm.ws_close_code == WS_INTERNAL_ERROR
        assert_no_leaks(norm.message, 'unknown WS key')


# ── Close code standardization ──


class TestCloseCodeStandardization:
    """Verify close codes are unique and consistent."""

    def test_unique_close_codes(self):
        codes = {
            WS_SESSION_NOT_FOUND,
            WS_SESSION_TERMINATED,
            WS_VALIDATION_ERROR,
            WS_RATE_LIMITED,
            WS_PROVIDER_UNAVAILABLE,
            WS_PROVIDER_TIMEOUT,
            WS_AUTH_REQUIRED,
        }
        assert len(codes) == 7  # All unique

    def test_close_codes_in_app_range(self):
        app_codes = [
            WS_SESSION_NOT_FOUND,
            WS_SESSION_TERMINATED,
            WS_VALIDATION_ERROR,
            WS_RATE_LIMITED,
            WS_PROVIDER_UNAVAILABLE,
            WS_PROVIDER_TIMEOUT,
            WS_AUTH_REQUIRED,
        ]
        for code in app_codes:
            assert 4000 <= code <= 4999, f'Code {code} not in app range'

    def test_internal_error_is_standard(self):
        assert WS_INTERNAL_ERROR == 1011


# ── PTY bridge error semantics ──


class TestPtyBridgeErrorSemantics:

    def test_error_message_safe(self):
        bridge = PTYBridge()
        msg = bridge.build_error_message('Connection to upstream failed')
        assert_no_leaks(msg['message'], 'PTY error message')

    def test_session_not_found_safe(self):
        bridge = PTYBridge()
        msg = bridge.build_session_not_found()
        assert msg['type'] == 'session_not_found'

    def test_close_codes_mapped(self):
        bridge = PTYBridge()
        for key in ['session_not_found', 'session_terminated']:
            code = bridge.close_code_for_error(key)
            assert 4000 <= code <= 4999

    def test_unknown_close_code_safe(self):
        bridge = PTYBridge()
        code = bridge.close_code_for_error('unknown_internal_thing')
        assert code == WS_INTERNAL_ERROR


# ── Chat bridge error semantics ──


class TestChatBridgeErrorSemantics:

    def test_error_message_safe(self):
        bridge = ChatBridge()
        msg = bridge.build_error_message('Service temporarily unavailable')
        assert msg['type'] == 'system'
        assert msg['subtype'] == 'error'
        assert_no_leaks(msg['message'], 'Chat error message')

    def test_session_not_found_safe(self):
        bridge = ChatBridge()
        msg = bridge.build_session_not_found()
        assert 'not found' in msg['message'].lower()
        assert_no_leaks(msg['message'], 'Chat session not found')

    def test_close_codes_mapped(self):
        bridge = ChatBridge()
        for key in ['session_not_found', 'session_terminated']:
            code = bridge.close_code_for_error(key)
            assert 4000 <= code <= 4999


# ── HTTP delegation error mapping ──


class TestDelegationErrorMapping:
    """Verify delegation layer maps upstream errors safely."""

    @pytest.mark.parametrize('upstream_status', [400, 403, 404, 409, 422, 429, 500, 502, 503])
    def test_upstream_mapped_safely(self, upstream_status):
        resp = map_upstream_status(upstream_status)
        if resp.json_body:
            body_str = json.dumps(resp.json_body)
            assert_no_leaks(body_str, f'Delegation {upstream_status}')

    def test_5xx_never_pass_through(self):
        """Upstream 5xx should never be forwarded as-is."""
        for status in [500, 502, 503, 504]:
            resp = map_upstream_status(status)
            # 5xx should map to 502 (provider_error) or 503/504
            assert resp.status_code in {502, 503, 504}

    def test_unknown_status_safe(self):
        resp = map_upstream_status(599)
        assert resp.status_code == 502  # Maps to provider_error

    def test_error_body_never_empty(self):
        for status in [400, 404, 500]:
            resp = map_upstream_status(status)
            if resp.json_body:
                assert 'error' in resp.json_body
                assert len(resp.json_body['error']) > 0


# ── Cross-cutting leak scenarios ──


class TestCrossCuttingLeakPrevention:
    """Test various real-world internal detail patterns don't leak."""

    INTERNAL_DETAILS = [
        'httpx.ConnectError: Connection refused at localhost:9000',
        'aiohttp.ClientError: Cannot connect to host workspace:8080',
        'grpc.StatusCode.UNAVAILABLE: DNS resolution failed for sprites-svc:50051',
        'socket.timeout: timed out connecting to 10.0.1.42:3000',
        'Traceback (most recent call last):\n  File "/app/server.py", line 42',
        'urllib3.exceptions.MaxRetryError: HTTPConnectionPool(host=\'192.168.1.100\')',
        'requests.exceptions.ConnectionError: HTTPConnectionPool',
        'ECONNREFUSED 127.0.0.1:9000',
    ]

    @pytest.mark.parametrize('detail', INTERNAL_DETAILS)
    def test_http_error_no_leak(self, detail):
        norm = normalize_http_error('provider_error', internal_detail=detail)
        assert_no_leaks(norm.message, f'HTTP with detail: {detail[:30]}')
        body = error_response_body(norm)
        assert_no_leaks(json.dumps(body), f'HTTP body with detail: {detail[:30]}')

    @pytest.mark.parametrize('detail', INTERNAL_DETAILS)
    def test_ws_error_no_leak(self, detail):
        norm = normalize_ws_error('ws_provider_unavailable', internal_detail=detail)
        assert_no_leaks(norm.message, f'WS with detail: {detail[:30]}')


# ── Retry-after semantics ──


class TestRetryAfterSemantics:
    """Verify retry-after is only set when appropriate."""

    def test_rate_limited_has_retry_after(self):
        norm = normalize_http_error('rate_limited')
        assert norm.retry_after > 0
        body = error_response_body(norm)
        assert 'retry_after' in body

    def test_provider_unavailable_has_retry_after(self):
        norm = normalize_http_error('provider_unavailable')
        assert norm.retry_after > 0

    def test_not_found_no_retry_after(self):
        norm = normalize_http_error('not_found')
        assert norm.retry_after == 0
        body = error_response_body(norm)
        assert 'retry_after' not in body

    def test_validation_no_retry_after(self):
        norm = normalize_http_error('bad_request')
        assert norm.retry_after == 0

    def test_ws_rate_limited_has_retry_after(self):
        norm = normalize_ws_error('ws_rate_limited')
        assert norm.retry_after > 0

    def test_ws_provider_unavailable_has_retry_after(self):
        norm = normalize_ws_error('ws_provider_unavailable')
        assert norm.retry_after > 0
