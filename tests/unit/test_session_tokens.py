"""Unit tests for opaque session tokens."""
import base64
import hashlib
import hmac
import json
import time
import pytest

from boring_ui.api.session_tokens import (
    DEFAULT_MAX_RENEWALS,
    DEFAULT_TOKEN_TTL,
    SessionTokenError,
    SessionTokenPayload,
    issue_session_token,
    renew_session_token,
    validate_session_token,
)


SECRET = 'test-secret-at-least-32-characters-long!'
NOW = 1700000000.0


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(data: str) -> bytes:
    padding = '=' * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _resign(token: str, secret: str, payload_override: dict | None = None) -> str:
    header_b64, payload_b64, _ = token.split('.')
    payload = json.loads(_b64url_decode(payload_b64))
    if payload_override is not None:
        payload = payload_override
    new_payload_b64 = _b64url_encode(json.dumps(payload, sort_keys=True).encode())
    message = f'{header_b64}.{new_payload_b64}'
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return f'{header_b64}.{new_payload_b64}.{signature}'


class TestIssueToken:

    def test_returns_string(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        assert isinstance(token, str)

    def test_has_three_parts(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        assert len(token.split('.')) == 3

    def test_deterministic_with_same_inputs(self):
        t1 = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        t2 = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        assert t1 == t2

    def test_different_sessions_produce_different_tokens(self):
        t1 = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        t2 = issue_session_token(SECRET, 'sess-2', 'shell', now=NOW)
        assert t1 != t2

    def test_different_secrets_produce_different_tokens(self):
        t1 = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        t2 = issue_session_token('other-secret-32-characters-long!', 'sess-1', 'shell', now=NOW)
        assert t1 != t2

    def test_custom_ttl(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', ttl=300, now=NOW)
        payload = validate_session_token(token, SECRET, now=NOW)
        assert payload.expires_at == NOW + 300

    def test_rejects_empty_secret(self):
        with pytest.raises(SessionTokenError, match='secret'):
            issue_session_token('', 'sess-1', 'shell', now=NOW)

    def test_rejects_empty_session_id(self):
        with pytest.raises(SessionTokenError, match='sid'):
            issue_session_token(SECRET, '', 'shell', now=NOW)

    def test_rejects_non_positive_ttl(self):
        with pytest.raises(SessionTokenError, match='ttl'):
            issue_session_token(SECRET, 'sess-1', 'shell', ttl=0, now=NOW)


class TestValidateToken:

    def test_valid_token(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        payload = validate_session_token(token, SECRET, now=NOW)
        assert payload.session_id == 'sess-1'
        assert payload.template_id == 'shell'
        assert payload.issued_at == NOW
        assert payload.renewal_count == 0

    def test_expired_token(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', ttl=60, now=NOW)
        with pytest.raises(SessionTokenError, match='expired'):
            validate_session_token(token, SECRET, now=NOW + 61)

    def test_wrong_secret(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        with pytest.raises(SessionTokenError, match='signature'):
            validate_session_token(token, 'wrong-secret-32-characters-long!', now=NOW)

    def test_tampered_payload(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        parts = token.split('.')
        # Tamper with payload
        parts[1] = parts[1] + 'x'
        tampered = '.'.join(parts)
        with pytest.raises(SessionTokenError, match='signature'):
            validate_session_token(tampered, SECRET, now=NOW)

    def test_malformed_token_no_dots(self):
        with pytest.raises(SessionTokenError, match='Malformed'):
            validate_session_token('not-a-token', SECRET)

    def test_malformed_token_two_parts(self):
        with pytest.raises(SessionTokenError, match='Malformed'):
            validate_session_token('part1.part2', SECRET)

    def test_not_expired_at_boundary(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', ttl=60, now=NOW)
        # At exactly expiry time, still valid
        payload = validate_session_token(token, SECRET, now=NOW + 60)
        assert payload.session_id == 'sess-1'

    def test_expired_just_after(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', ttl=60, now=NOW)
        with pytest.raises(SessionTokenError, match='expired'):
            validate_session_token(token, SECRET, now=NOW + 60.001)

    def test_rejects_non_numeric_exp(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        bad = _resign(token, SECRET, payload_override={
            'sid': 'sess-1',
            'tid': 'shell',
            'iat': NOW,
            'exp': 'tomorrow',
            'rnw': 0,
        })
        with pytest.raises(SessionTokenError, match='exp'):
            validate_session_token(bad, SECRET, now=NOW)

    def test_rejects_negative_renewal_count(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        bad = _resign(token, SECRET, payload_override={
            'sid': 'sess-1',
            'tid': 'shell',
            'iat': NOW,
            'exp': NOW + 60,
            'rnw': -1,
        })
        with pytest.raises(SessionTokenError, match='rnw'):
            validate_session_token(bad, SECRET, now=NOW)

    def test_rejects_invalid_time_window(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        bad = _resign(token, SECRET, payload_override={
            'sid': 'sess-1',
            'tid': 'shell',
            'iat': NOW + 10,
            'exp': NOW + 5,
            'rnw': 0,
        })
        with pytest.raises(SessionTokenError, match='iat'):
            validate_session_token(bad, SECRET, now=NOW)


class TestSessionTokenPayload:

    def test_is_expired(self):
        p = SessionTokenPayload(
            session_id='s', template_id='t',
            issued_at=NOW, expires_at=NOW - 1,
            renewal_count=0,
        )
        assert p.is_expired

    def test_not_expired(self):
        p = SessionTokenPayload(
            session_id='s', template_id='t',
            issued_at=NOW, expires_at=time.time() + 3600,
            renewal_count=0,
        )
        assert not p.is_expired

    def test_ttl_remaining(self):
        future = time.time() + 100
        p = SessionTokenPayload(
            session_id='s', template_id='t',
            issued_at=NOW, expires_at=future,
            renewal_count=0,
        )
        assert p.ttl_remaining > 0
        assert p.ttl_remaining <= 100

    def test_ttl_remaining_expired(self):
        p = SessionTokenPayload(
            session_id='s', template_id='t',
            issued_at=NOW, expires_at=NOW - 1,
            renewal_count=0,
        )
        assert p.ttl_remaining == 0.0

    def test_frozen(self):
        p = SessionTokenPayload(
            session_id='s', template_id='t',
            issued_at=NOW, expires_at=NOW + 60,
            renewal_count=0,
        )
        with pytest.raises(AttributeError):
            p.session_id = 'other'


class TestRenewToken:

    def test_renew_preserves_session_id(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        renewed = renew_session_token(token, SECRET, now=NOW + 10)
        payload = validate_session_token(renewed, SECRET, now=NOW + 10)
        assert payload.session_id == 'sess-1'
        assert payload.template_id == 'shell'

    def test_renew_increments_count(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        renewed = renew_session_token(token, SECRET, now=NOW + 10)
        payload = validate_session_token(renewed, SECRET, now=NOW + 10)
        assert payload.renewal_count == 1

    def test_renew_extends_ttl(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', ttl=60, now=NOW)
        renewed = renew_session_token(token, SECRET, ttl=120, now=NOW + 30)
        payload = validate_session_token(renewed, SECRET, now=NOW + 30)
        assert payload.expires_at == NOW + 30 + 120

    def test_renew_produces_different_token(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        renewed = renew_session_token(token, SECRET, now=NOW + 10)
        assert renewed != token

    def test_max_renewals_enforced(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        # Renew up to max
        for i in range(DEFAULT_MAX_RENEWALS):
            token = renew_session_token(token, SECRET, now=NOW + i + 1)
        # Next renewal should fail
        with pytest.raises(SessionTokenError, match='Maximum renewals'):
            renew_session_token(token, SECRET, now=NOW + DEFAULT_MAX_RENEWALS + 1)

    def test_custom_max_renewals(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        token = renew_session_token(token, SECRET, max_renewals=1, now=NOW + 1)
        with pytest.raises(SessionTokenError, match='Maximum renewals'):
            renew_session_token(token, SECRET, max_renewals=1, now=NOW + 2)

    def test_renew_expired_token_fails(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', ttl=60, now=NOW)
        with pytest.raises(SessionTokenError, match='expired'):
            renew_session_token(token, SECRET, now=NOW + 61)

    def test_renew_with_wrong_secret_fails(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        with pytest.raises(SessionTokenError, match='signature'):
            renew_session_token(token, 'wrong-secret-32-characters-long!', now=NOW)

    def test_chain_renewals(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', ttl=60, now=NOW)
        for i in range(5):
            token = renew_session_token(token, SECRET, ttl=60, now=NOW + (i + 1) * 30)
        payload = validate_session_token(token, SECRET, now=NOW + 150)
        assert payload.renewal_count == 5
        assert payload.session_id == 'sess-1'

    def test_renew_rejects_non_positive_ttl(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        with pytest.raises(SessionTokenError, match='ttl'):
            renew_session_token(token, SECRET, ttl=0, now=NOW + 1)

    def test_renew_rejects_negative_max_renewals(self):
        token = issue_session_token(SECRET, 'sess-1', 'shell', now=NOW)
        with pytest.raises(SessionTokenError, match='max_renewals'):
            renew_session_token(token, SECRET, max_renewals=-1, now=NOW + 1)


class TestRoundtrip:

    def test_issue_validate_roundtrip(self):
        token = issue_session_token(SECRET, 'exec-abc123', 'claude', ttl=7200, now=NOW)
        payload = validate_session_token(token, SECRET, now=NOW)
        assert payload.session_id == 'exec-abc123'
        assert payload.template_id == 'claude'
        assert payload.expires_at == NOW + 7200
        assert payload.renewal_count == 0
        assert payload.version == 1

    def test_issue_renew_validate_roundtrip(self):
        t1 = issue_session_token(SECRET, 'exec-xyz', 'shell', now=NOW)
        t2 = renew_session_token(t1, SECRET, ttl=1800, now=NOW + 100)
        payload = validate_session_token(t2, SECRET, now=NOW + 100)
        assert payload.session_id == 'exec-xyz'
        assert payload.renewal_count == 1
        assert payload.expires_at == NOW + 100 + 1800
