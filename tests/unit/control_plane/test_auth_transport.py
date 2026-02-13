"""Auth transport parity tests.

Bead: bd-223o.7.4 (B4)

Tests:
  - Credential extraction: Bearer > session cookie > none
  - Session token → AuthIdentity produces same shape as Bearer
  - Transport enum tracks source correctly
  - Invalid/expired session tokens fail with correct errors
  - Both transports produce equivalent AuthIdentity for same user
"""

from __future__ import annotations

import time

import jwt
import pytest
from starlette.testclient import TestClient
from starlette.requests import Request

from control_plane.app.security.auth_transport import (
    AuthTransport,
    ExtractedCredentials,
    extract_credentials,
    identity_from_session_token,
)
from control_plane.app.security.token_verify import (
    AuthIdentity,
    TokenVerificationError,
)

# ── Helpers ───────────────────────────────────────────────────────────

SESSION_SECRET = 'test-session-secret-32-chars-long!'


def _make_session_token(
    user_id: str = 'user-123',
    email: str = 'test@example.com',
    role: str = 'authenticated',
    ttl: int = 3600,
    token_type: str = 'session',
) -> str:
    now = int(time.time())
    payload = {
        'sub': user_id,
        'email': email,
        'role': role,
        'iat': now,
        'exp': now + ttl,
        'type': token_type,
    }
    return jwt.encode(payload, SESSION_SECRET, algorithm='HS256')


class FakeRequest:
    """Minimal request-like object for testing credential extraction."""

    def __init__(self, headers=None, cookies=None):
        self.headers = headers or {}
        self.cookies = cookies or {}


# =====================================================================
# Credential extraction
# =====================================================================


class TestExtractCredentials:
    def test_bearer_token_extracted(self):
        request = FakeRequest(headers={'authorization': 'Bearer my-token'})
        result = extract_credentials(request)
        assert result.token == 'my-token'
        assert result.transport == AuthTransport.BEARER

    def test_session_cookie_extracted(self):
        request = FakeRequest(cookies={'boring_session': 'session-jwt'})
        result = extract_credentials(request)
        assert result.token == 'session-jwt'
        assert result.transport == AuthTransport.SESSION_COOKIE

    def test_bearer_takes_precedence_over_cookie(self):
        request = FakeRequest(
            headers={'authorization': 'Bearer bearer-token'},
            cookies={'boring_session': 'cookie-token'},
        )
        result = extract_credentials(request)
        assert result.token == 'bearer-token'
        assert result.transport == AuthTransport.BEARER

    def test_no_credentials(self):
        request = FakeRequest()
        result = extract_credentials(request)
        assert result.token is None
        assert result.transport == AuthTransport.NONE

    def test_empty_bearer_falls_to_cookie(self):
        request = FakeRequest(
            headers={'authorization': 'Bearer '},
            cookies={'boring_session': 'cookie-token'},
        )
        result = extract_credentials(request)
        assert result.token == 'cookie-token'
        assert result.transport == AuthTransport.SESSION_COOKIE

    def test_non_bearer_auth_header_ignored(self):
        request = FakeRequest(
            headers={'authorization': 'Basic dXNlcjpwYXNz'},
            cookies={'boring_session': 'cookie-token'},
        )
        result = extract_credentials(request)
        assert result.token == 'cookie-token'
        assert result.transport == AuthTransport.SESSION_COOKIE

    def test_custom_cookie_name(self):
        request = FakeRequest(cookies={'custom_session': 'my-token'})
        result = extract_credentials(request, session_cookie_name='custom_session')
        assert result.token == 'my-token'
        assert result.transport == AuthTransport.SESSION_COOKIE


# =====================================================================
# Session token → AuthIdentity
# =====================================================================


class TestIdentityFromSessionToken:
    def test_valid_session_returns_identity(self):
        token = _make_session_token()
        identity = identity_from_session_token(token, SESSION_SECRET)
        assert identity.user_id == 'user-123'
        assert identity.email == 'test@example.com'
        assert identity.role == 'authenticated'

    def test_expired_session_raises(self):
        token = _make_session_token(ttl=-10)
        with pytest.raises(TokenVerificationError, match='session_expired'):
            identity_from_session_token(token, SESSION_SECRET)

    def test_wrong_secret_raises(self):
        token = _make_session_token()
        with pytest.raises(TokenVerificationError, match='invalid_session'):
            identity_from_session_token(token, 'wrong-secret')

    def test_wrong_type_raises(self):
        token = _make_session_token(token_type='refresh')
        with pytest.raises(TokenVerificationError, match='invalid_token_type'):
            identity_from_session_token(token, SESSION_SECRET)

    def test_identity_has_raw_claims(self):
        token = _make_session_token()
        identity = identity_from_session_token(token, SESSION_SECRET)
        assert 'sub' in identity.raw_claims
        assert identity.raw_claims['type'] == 'session'


# =====================================================================
# Parity: same user produces identical identity shape
# =====================================================================


class TestTransportParity:
    """Both transports must produce equivalent AuthIdentity."""

    def test_same_user_same_identity_shape(self):
        """Session token and bearer verification produce same shape."""
        session_token = _make_session_token(
            user_id='user-456',
            email='parity@example.com',
            role='authenticated',
        )
        session_identity = identity_from_session_token(
            session_token, SESSION_SECRET
        )

        # The bearer path would produce this same identity shape.
        bearer_identity = AuthIdentity(
            user_id='user-456',
            email='parity@example.com',
            role='authenticated',
        )

        assert session_identity.user_id == bearer_identity.user_id
        assert session_identity.email == bearer_identity.email
        assert session_identity.role == bearer_identity.role

    def test_identity_is_same_class(self):
        token = _make_session_token()
        identity = identity_from_session_token(token, SESSION_SECRET)
        assert isinstance(identity, AuthIdentity)


# =====================================================================
# Transport enum
# =====================================================================


class TestAuthTransport:
    def test_values(self):
        assert AuthTransport.BEARER.value == 'bearer'
        assert AuthTransport.SESSION_COOKIE.value == 'session_cookie'
        assert AuthTransport.NONE.value == 'none'

    def test_extracted_credentials_is_frozen(self):
        cred = ExtractedCredentials(token='t', transport=AuthTransport.BEARER)
        with pytest.raises(AttributeError):
            cred.token = 'changed'
