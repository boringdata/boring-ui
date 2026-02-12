"""Unit tests for cross-client error normalization."""
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


class TestNormalizedError:

    def test_frozen(self):
        e = NormalizedError(
            category=ErrorCategory.VALIDATION,
            http_status=400,
            message='test',
        )
        with pytest.raises(AttributeError):
            e.message = 'modified'

    def test_defaults(self):
        e = NormalizedError(
            category=ErrorCategory.INTERNAL,
            http_status=500,
            message='error',
        )
        assert e.ws_close_code == 0
        assert e.retry_after == 0


class TestNormalizeHttpError:

    def test_bad_request(self):
        e = normalize_http_error('bad_request')
        assert e.http_status == 400
        assert e.category == ErrorCategory.VALIDATION

    def test_not_found(self):
        e = normalize_http_error('not_found')
        assert e.http_status == 404
        assert e.category == ErrorCategory.NOT_FOUND

    def test_conflict(self):
        e = normalize_http_error('conflict')
        assert e.http_status == 409

    def test_validation_error(self):
        e = normalize_http_error('validation_error')
        assert e.http_status == 422

    def test_unauthorized(self):
        e = normalize_http_error('unauthorized')
        assert e.http_status == 403
        assert e.category == ErrorCategory.AUTH

    def test_rate_limited(self):
        e = normalize_http_error('rate_limited')
        assert e.http_status == 429
        assert e.retry_after == 60

    def test_provider_error(self):
        e = normalize_http_error('provider_error')
        assert e.http_status == 502
        assert e.category == ErrorCategory.PROVIDER_ERROR

    def test_provider_unavailable(self):
        e = normalize_http_error('provider_unavailable')
        assert e.http_status == 503
        assert e.retry_after == 5

    def test_provider_timeout(self):
        e = normalize_http_error('provider_timeout')
        assert e.http_status == 504

    def test_transport_error(self):
        e = normalize_http_error('transport_error')
        assert e.http_status == 502

    def test_internal_error(self):
        e = normalize_http_error('internal_error')
        assert e.http_status == 500

    def test_unknown_key_defaults_to_500(self):
        e = normalize_http_error('totally_unknown')
        assert e.http_status == 500
        assert e.category == ErrorCategory.INTERNAL

    def test_message_never_leaks_internals(self):
        e = normalize_http_error(
            'provider_error',
            internal_detail='httpx.ConnectError: refused at localhost:9000',
        )
        assert 'localhost' not in e.message
        assert 'httpx' not in e.message
        assert '9000' not in e.message


class TestNormalizeWsError:

    def test_session_not_found(self):
        e = normalize_ws_error('session_not_found')
        assert e.ws_close_code == WS_SESSION_NOT_FOUND
        assert e.category == ErrorCategory.NOT_FOUND

    def test_session_terminated(self):
        e = normalize_ws_error('session_terminated')
        assert e.ws_close_code == WS_SESSION_TERMINATED

    def test_provider_unknown(self):
        e = normalize_ws_error('provider_unknown')
        assert e.ws_close_code == 4003

    def test_ws_validation_error(self):
        e = normalize_ws_error('ws_validation_error')
        assert e.ws_close_code == WS_VALIDATION_ERROR

    def test_ws_rate_limited(self):
        e = normalize_ws_error('ws_rate_limited')
        assert e.ws_close_code == WS_RATE_LIMITED
        assert e.retry_after == 60

    def test_ws_provider_unavailable(self):
        e = normalize_ws_error('ws_provider_unavailable')
        assert e.ws_close_code == WS_PROVIDER_UNAVAILABLE
        assert e.retry_after == 5

    def test_ws_provider_timeout(self):
        e = normalize_ws_error('ws_provider_timeout')
        assert e.ws_close_code == WS_PROVIDER_TIMEOUT

    def test_ws_auth_required(self):
        e = normalize_ws_error('ws_auth_required')
        assert e.ws_close_code == WS_AUTH_REQUIRED

    def test_unknown_ws_key_defaults_to_1011(self):
        e = normalize_ws_error('totally_unknown')
        assert e.ws_close_code == WS_INTERNAL_ERROR
        assert e.category == ErrorCategory.INTERNAL

    def test_ws_message_never_leaks_internals(self):
        e = normalize_ws_error(
            'ws_provider_unavailable',
            internal_detail='Connection to workspace:9000 refused',
        )
        assert 'workspace' not in e.message
        assert '9000' not in e.message


class TestNormalizeHttpStatus:

    def test_400(self):
        e = normalize_http_status(400)
        assert e.http_status == 400

    def test_404(self):
        e = normalize_http_status(404)
        assert e.http_status == 404

    def test_409(self):
        e = normalize_http_status(409)
        assert e.http_status == 409

    def test_422(self):
        e = normalize_http_status(422)
        assert e.http_status == 422

    def test_429(self):
        e = normalize_http_status(429)
        assert e.http_status == 429

    def test_500(self):
        e = normalize_http_status(500)
        assert e.http_status == 502  # Internal maps to 502

    def test_502(self):
        e = normalize_http_status(502)
        assert e.http_status == 502

    def test_503(self):
        e = normalize_http_status(503)
        assert e.http_status == 503

    def test_504(self):
        e = normalize_http_status(504)
        assert e.http_status == 504

    def test_unknown_5xx_maps_to_502(self):
        e = normalize_http_status(599)
        assert e.http_status == 502

    def test_401_maps_to_403(self):
        e = normalize_http_status(401)
        assert e.http_status == 403

    def test_unknown_4xx(self):
        e = normalize_http_status(418)
        assert e.http_status == 500  # Falls through to internal_error


class TestErrorResponseBody:

    def test_basic_body(self):
        e = NormalizedError(
            category=ErrorCategory.NOT_FOUND,
            http_status=404,
            message='Resource not found',
        )
        body = error_response_body(e)
        assert body['error'] == 'Resource not found'
        assert body['category'] == 'not_found'
        assert 'retry_after' not in body

    def test_includes_retry_after(self):
        e = NormalizedError(
            category=ErrorCategory.RATE_LIMIT,
            http_status=429,
            message='Rate limited',
            retry_after=60,
        )
        body = error_response_body(e)
        assert body['retry_after'] == 60

    def test_no_retry_after_when_zero(self):
        e = NormalizedError(
            category=ErrorCategory.INTERNAL,
            http_status=500,
            message='Error',
            retry_after=0,
        )
        body = error_response_body(e)
        assert 'retry_after' not in body

    def test_body_has_no_internal_details(self):
        e = normalize_http_error(
            'provider_error',
            internal_detail='httpx.ConnectError at 192.168.1.1:9000',
        )
        body = error_response_body(e)
        assert '192.168' not in str(body)
        assert 'httpx' not in str(body)
