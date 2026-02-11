"""Tests for error codes and mapping functions (bd-1adh.4.2)."""

import pytest
from boring_ui.api.error_codes import (
    ErrorCode,
    TransportError,
    map_sprites_connect_error,
    map_sprites_handshake_error,
    map_relay_timeout_error,
    map_protocol_parse_error,
    map_size_exceeded_error,
    map_http_status_to_error,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_error_codes_exist(self):
        """All expected error codes are defined."""
        assert ErrorCode.SPRITES_HANDSHAKE_TIMEOUT.value == "sprites_handshake_timeout"
        assert ErrorCode.SPRITES_RELAY_LOST.value == "sprites_relay_lost"
        assert ErrorCode.LOCAL_API_UNAVAILABLE.value == "local_api_unavailable"
        assert ErrorCode.LOCAL_API_TIMEOUT.value == "local_api_timeout"
        assert ErrorCode.TRANSPORT_RETRY_EXHAUSTED.value == "transport_retry_exhausted"

    def test_error_code_values_are_strings(self):
        """Error codes have string values for API serialization."""
        for code in ErrorCode:
            assert isinstance(code.value, str)
            assert len(code.value) > 0


class TestTransportError:
    """Tests for TransportError dataclass."""

    def test_transport_error_creation(self):
        """Create TransportError with all fields."""
        error = TransportError(
            code=ErrorCode.SPRITES_HANDSHAKE_TIMEOUT,
            message="Handshake timed out",
            http_status=502,
            retryable=True,
            details={"elapsed_sec": 5.0},
        )

        assert error.code == ErrorCode.SPRITES_HANDSHAKE_TIMEOUT
        assert error.message == "Handshake timed out"
        assert error.http_status == 502
        assert error.retryable is True
        assert error.details["elapsed_sec"] == 5.0

    def test_transport_error_to_dict(self):
        """Serialize TransportError to dict."""
        error = TransportError(
            code=ErrorCode.SPRITES_RELAY_LOST,
            message="Connection lost",
            http_status=504,
            retryable=True,
            details={"attempt": 2},
        )

        error_dict = error.to_dict()

        assert error_dict["error_code"] == "sprites_relay_lost"
        assert error_dict["message"] == "Connection lost"
        assert error_dict["http_status"] == 504
        assert error_dict["retryable"] is True
        assert error_dict["details"]["attempt"] == 2

    def test_transport_error_to_dict_no_details(self):
        """Serialize TransportError with no details."""
        error = TransportError(
            code=ErrorCode.LOCAL_API_UNAVAILABLE,
            message="API not available",
            http_status=503,
            retryable=True,
        )

        error_dict = error.to_dict()

        assert error_dict["details"] == {}


class TestErrorMapping:
    """Tests for error mapping functions."""

    def test_map_sprites_connect_timeout(self):
        """Map connection timeout to Sprites error."""
        error = map_sprites_connect_error(
            TimeoutError("Connection timed out"),
            elapsed_sec=5.1,
        )

        assert error.code == ErrorCode.SPRITES_CONNECT_TIMEOUT
        assert error.http_status == 502
        assert error.retryable is True
        assert error.details["elapsed_sec"] == 5.1

    def test_map_sprites_connect_failure(self):
        """Map connection failure (non-timeout) to Sprites error."""
        error = map_sprites_connect_error(
            ConnectionRefusedError("Connection refused"),
            elapsed_sec=0.1,
        )

        assert error.code == ErrorCode.SPRITES_RELAY_LOST
        assert error.http_status == 502
        assert error.retryable is True

    def test_map_sprites_handshake_timeout(self):
        """Map handshake timeout."""
        error = map_sprites_handshake_error(
            TimeoutError("Handshake timeout"),
            elapsed_sec=5.0,
        )

        assert error.code == ErrorCode.SPRITES_HANDSHAKE_TIMEOUT
        assert error.http_status == 502
        assert error.retryable is True

    def test_map_sprites_handshake_invalid(self):
        """Map invalid handshake response."""
        error = map_sprites_handshake_error(
            ValueError("Invalid JSON"),
            elapsed_sec=0.5,
        )

        assert error.code == ErrorCode.SPRITES_HANDSHAKE_INVALID
        assert error.http_status == 502
        assert error.retryable is False

    def test_map_relay_timeout_error(self):
        """Map relay timeout error."""
        error = map_relay_timeout_error(elapsed_sec=30.5)

        assert error.code == ErrorCode.SPRITES_RELAY_LOST
        assert error.http_status == 504
        assert error.retryable is True
        assert error.details["elapsed_sec"] == 30.5

    def test_map_protocol_parse_error(self):
        """Map protocol parse error."""
        error = map_protocol_parse_error(
            ValueError("Invalid status line"),
            reason="No CRLF in status line",
        )

        assert error.code == ErrorCode.LOCAL_API_PROTOCOL_ERROR
        assert error.http_status == 502
        assert error.retryable is False
        assert error.details["reason"] == "No CRLF in status line"

    def test_map_size_exceeded_error(self):
        """Map response size exceeded error."""
        error = map_size_exceeded_error(
            actual_bytes=15_000_000,
            max_bytes=10_000_000,
        )

        assert error.code == ErrorCode.TRANSPORT_SIZE_EXCEEDED
        assert error.http_status == 502
        assert error.retryable is False
        assert error.details["actual_bytes"] == 15_000_000
        assert error.details["max_bytes"] == 10_000_000

    def test_map_http_status_502(self):
        """Map HTTP 502 status to retryable error."""
        error = map_http_status_to_error(502)

        assert error.code == ErrorCode.HTTP_STATUS_502
        assert error.http_status == 502
        assert error.retryable is True

    def test_map_http_status_503(self):
        """Map HTTP 503 status to retryable error."""
        error = map_http_status_to_error(503)

        assert error.code == ErrorCode.HTTP_STATUS_503
        assert error.http_status == 503
        assert error.retryable is True

    def test_map_http_status_504(self):
        """Map HTTP 504 status to retryable error."""
        error = map_http_status_to_error(504)

        assert error.code == ErrorCode.HTTP_STATUS_504
        assert error.http_status == 504
        assert error.retryable is True

    def test_map_http_status_400(self):
        """Map HTTP 400 status to non-retryable error."""
        error = map_http_status_to_error(400)

        assert error.code == ErrorCode.HTTP_STATUS_400
        assert error.http_status == 400
        assert error.retryable is False

    def test_map_http_status_401(self):
        """Map HTTP 401 status to non-retryable error."""
        error = map_http_status_to_error(401)

        assert error.code == ErrorCode.HTTP_STATUS_401
        assert error.http_status == 401
        assert error.retryable is False

    def test_map_http_status_403(self):
        """Map HTTP 403 status to non-retryable error."""
        error = map_http_status_to_error(403)

        assert error.code == ErrorCode.HTTP_STATUS_403
        assert error.http_status == 403
        assert error.retryable is False

    def test_map_http_status_404(self):
        """Map HTTP 404 status to non-retryable error."""
        error = map_http_status_to_error(404)

        assert error.code == ErrorCode.HTTP_STATUS_404
        assert error.http_status == 404
        assert error.retryable is False

    def test_map_http_status_500(self):
        """Map HTTP 500 status to retryable error."""
        error = map_http_status_to_error(500)

        assert error.code == ErrorCode.HTTP_STATUS_500
        assert error.http_status == 500
        assert error.retryable is True

    def test_map_http_status_unknown(self):
        """Map unknown HTTP status code."""
        error = map_http_status_to_error(418)

        assert error.code == ErrorCode.LOCAL_API_UNAVAILABLE
        assert error.http_status == 418
        assert error.retryable is False

    def test_map_http_status_5xx_unknown(self):
        """Map unknown 5xx status code as retryable."""
        error = map_http_status_to_error(599)

        assert error.code == ErrorCode.LOCAL_API_UNAVAILABLE
        assert error.http_status == 599
        assert error.retryable is True
