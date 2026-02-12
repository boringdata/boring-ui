"""Unit tests for secret redaction rules."""
import logging
import pytest

from boring_ui.api.secret_redaction import (
    MIN_SECRET_LENGTH,
    REDACTED,
    RedactingFilter,
    SafeErrorResponse,
    SecretRedactor,
    create_safe_error,
)


class TestSecretRedactor:

    def test_redacts_registered_secret(self):
        r = SecretRedactor()
        r.register('my-secret-token-12345')
        assert r.redact('Error with my-secret-token-12345') == f'Error with {REDACTED}'

    def test_redacts_multiple_occurrences(self):
        r = SecretRedactor()
        r.register('secret-value-abcdef')
        text = 'secret-value-abcdef and secret-value-abcdef'
        assert REDACTED in r.redact(text)
        assert 'secret-value-abcdef' not in r.redact(text)

    def test_ignores_short_secrets(self):
        r = SecretRedactor()
        r.register('short')  # < MIN_SECRET_LENGTH
        assert r.registered_count == 0

    def test_min_length_secret(self):
        r = SecretRedactor()
        secret = 'x' * MIN_SECRET_LENGTH
        r.register(secret)
        assert r.registered_count == 1

    def test_empty_secret(self):
        r = SecretRedactor()
        r.register('')
        assert r.registered_count == 0

    def test_register_many(self):
        r = SecretRedactor()
        r.register_many(['secret-one-abcdef', 'secret-two-ghijkl', 'short'])
        assert r.registered_count == 2

    def test_redact_empty_string(self):
        r = SecretRedactor()
        assert r.redact('') == ''

    def test_redact_no_secrets(self):
        r = SecretRedactor()
        r.register('my-secret-token-xyz')
        assert r.redact('nothing to see here') == 'nothing to see here'

    def test_is_clean_true(self):
        r = SecretRedactor()
        r.register('secret-token-abc123')
        assert r.is_clean('safe message') is True

    def test_is_clean_false(self):
        r = SecretRedactor()
        r.register('secret-token-abc123')
        assert r.is_clean('contains secret-token-abc123') is False

    def test_longest_first_redaction(self):
        r = SecretRedactor()
        r.register('secret-token')  # Shorter
        r.register('secret-token-extended')  # Longer
        result = r.redact('value: secret-token-extended')
        # Should redact the longer one completely, not leave '-extended'
        assert 'extended' not in result


class TestPatternMatching:

    def test_bearer_token(self):
        r = SecretRedactor()
        text = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.long.token'
        result = r.redact(text)
        assert 'eyJhbGci' not in result
        assert REDACTED in result

    def test_hmac_token(self):
        r = SecretRedactor()
        sig = 'a' * 64
        text = f'Auth: hmac-sha256:1700000000:{sig}'
        result = r.redact(text)
        assert sig not in result

    def test_hex_token(self):
        r = SecretRedactor()
        hex_token = 'a' * 40
        text = f'key={hex_token}'
        result = r.redact(text)
        assert hex_token not in result

    def test_github_token(self):
        r = SecretRedactor()
        text = 'token: ghp_' + 'A' * 36
        result = r.redact(text)
        assert 'ghp_' not in result

    def test_patterns_disabled(self):
        r = SecretRedactor(enable_pattern_matching=False)
        sig = 'a' * 64
        text = f'hmac-sha256:123:{sig}'
        assert r.redact(text) == text  # Not redacted

    def test_short_hex_not_redacted(self):
        r = SecretRedactor()
        text = 'hash: abcdef12'  # Only 8 chars hex, under 32
        # Should not match the 32+ char hex pattern
        assert r.redact(text) == text


class TestCreateSafeError:

    def test_redacts_detail(self):
        r = SecretRedactor()
        r.register('internal-token-xyz123')
        err = create_safe_error(
            500, 'Failed auth with internal-token-xyz123', r,
        )
        assert 'internal-token-xyz123' not in err.detail
        assert REDACTED in err.detail
        assert err.status_code == 500

    def test_preserves_error_id(self):
        r = SecretRedactor()
        err = create_safe_error(400, 'bad request', r, error_id='err-123')
        assert err.error_id == 'err-123'

    def test_clean_detail_unchanged(self):
        r = SecretRedactor()
        err = create_safe_error(404, 'Not found', r)
        assert err.detail == 'Not found'


class TestSafeErrorResponse:

    def test_frozen(self):
        err = SafeErrorResponse(status_code=500, detail='error')
        with pytest.raises(AttributeError):
            err.status_code = 200


class TestRedactingFilter:

    def test_redacts_log_message(self):
        r = SecretRedactor()
        r.register('secret-log-value-123')
        f = RedactingFilter(r)

        record = logging.LogRecord(
            'test', logging.ERROR, '', 0,
            'Error: secret-log-value-123 leaked', None, None,
        )
        f.filter(record)
        assert 'secret-log-value-123' not in record.msg
        assert REDACTED in record.msg

    def test_redacts_log_args_tuple(self):
        r = SecretRedactor()
        r.register('secret-arg-abcdefgh')
        f = RedactingFilter(r)

        record = logging.LogRecord(
            'test', logging.ERROR, '', 0,
            'Token: %s', ('secret-arg-abcdefgh',), None,
        )
        f.filter(record)
        assert 'secret-arg-abcdefgh' not in str(record.args)

    def test_redacts_log_args_dict(self):
        r = SecretRedactor()
        r.register('secret-dict-val-xyz')
        f = RedactingFilter(r)

        record = logging.LogRecord(
            'test', logging.ERROR, '', 0,
            'Token: %(token)s', None, None,
        )
        # Manually set args to a dict (as logging does internally for dict-style formatting)
        record.args = {'token': 'secret-dict-val-xyz'}
        f.filter(record)
        assert 'secret-dict-val-xyz' not in str(record.args)

    def test_non_string_args_preserved(self):
        r = SecretRedactor()
        f = RedactingFilter(r)

        record = logging.LogRecord(
            'test', logging.INFO, '', 0,
            'Count: %d', (42,), None,
        )
        f.filter(record)
        assert record.args == (42,)

    def test_always_returns_true(self):
        r = SecretRedactor()
        f = RedactingFilter(r)
        record = logging.LogRecord('test', logging.INFO, '', 0, 'msg', None, None)
        assert f.filter(record) is True
