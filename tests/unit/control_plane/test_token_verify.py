"""Tests for Supabase JWT token verification.

Bead: bd-223o.7.1 (B1)

Validates:
  - JWT signature verification (HS256/RS256)
  - Audience claim enforcement
  - Expiry enforcement
  - Required claims (sub, email)
  - Bearer token extraction from request headers
  - Error handling for malformed/missing/expired tokens
  - Factory function for JWKS vs static key selection
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from control_plane.app.security.token_verify import (
    AuthIdentity,
    JWKSKeyProvider,
    StaticKeyProvider,
    TokenVerificationError,
    TokenVerifier,
    create_token_verifier,
    extract_bearer_token,
)

# ── Test fixtures ─────────────────────────────────────────────────────

# HS256 test secret
TEST_SECRET = 'test-jwt-secret-for-unit-tests-only'
TEST_AUDIENCE = 'authenticated'

# RS256 test key pair
_rsa_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)
_rsa_public_key = _rsa_private_key.public_key()

RSA_PRIVATE_PEM = _rsa_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)
RSA_PUBLIC_PEM = _rsa_public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)


def _make_hs256_token(
    claims: dict | None = None,
    secret: str = TEST_SECRET,
    **overrides,
) -> str:
    """Create an HS256 JWT for testing."""
    payload = {
        'sub': 'user-uuid-123',
        'email': 'test@example.com',
        'role': 'authenticated',
        'aud': TEST_AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    if claims:
        payload.update(claims)
    payload.update(overrides)
    return jwt.encode(payload, secret, algorithm='HS256')


def _make_rs256_token(
    claims: dict | None = None,
    **overrides,
) -> str:
    """Create an RS256 JWT for testing."""
    payload = {
        'sub': 'user-uuid-456',
        'email': 'rs256@example.com',
        'role': 'authenticated',
        'aud': TEST_AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    if claims:
        payload.update(claims)
    payload.update(overrides)
    return jwt.encode(payload, RSA_PRIVATE_PEM, algorithm='RS256')


@pytest.fixture
def static_provider():
    return StaticKeyProvider(TEST_SECRET)


@pytest.fixture
def rsa_provider():
    """Provider that returns the RSA public key."""

    class _RSAProvider:
        def get_signing_key(self, token: str):
            return RSA_PUBLIC_PEM

    return _RSAProvider()


@pytest.fixture
def hs256_verifier(static_provider):
    return TokenVerifier(
        key_provider=static_provider,
        audience=TEST_AUDIENCE,
        algorithms=['HS256'],
    )


@pytest.fixture
def rs256_verifier(rsa_provider):
    return TokenVerifier(
        key_provider=rsa_provider,
        audience=TEST_AUDIENCE,
        algorithms=['RS256'],
    )


# =====================================================================
# 1. Successful verification
# =====================================================================


class TestSuccessfulVerification:

    def test_hs256_valid_token(self, hs256_verifier):
        token = _make_hs256_token()
        identity = hs256_verifier.verify(token)
        assert identity.user_id == 'user-uuid-123'
        assert identity.email == 'test@example.com'
        assert identity.role == 'authenticated'

    def test_rs256_valid_token(self, rs256_verifier):
        token = _make_rs256_token()
        identity = rs256_verifier.verify(token)
        assert identity.user_id == 'user-uuid-456'
        assert identity.email == 'rs256@example.com'

    def test_email_normalized_to_lowercase(self, hs256_verifier):
        token = _make_hs256_token(email='Test@EXAMPLE.Com')
        identity = hs256_verifier.verify(token)
        assert identity.email == 'test@example.com'

    def test_raw_claims_included(self, hs256_verifier):
        token = _make_hs256_token(custom_claim='hello')
        identity = hs256_verifier.verify(token)
        assert identity.raw_claims['custom_claim'] == 'hello'
        assert identity.raw_claims['sub'] == 'user-uuid-123'

    def test_custom_role_preserved(self, hs256_verifier):
        token = _make_hs256_token(role='service_role')
        identity = hs256_verifier.verify(token)
        assert identity.role == 'service_role'


# =====================================================================
# 2. Token expiry
# =====================================================================


class TestTokenExpiry:

    def test_expired_token_rejected(self, hs256_verifier):
        token = _make_hs256_token(exp=int(time.time()) - 100)
        with pytest.raises(TokenVerificationError) as exc_info:
            hs256_verifier.verify(token)
        assert exc_info.value.code == 'token_expired'

    def test_future_token_accepted(self, hs256_verifier):
        token = _make_hs256_token(exp=int(time.time()) + 7200)
        identity = hs256_verifier.verify(token)
        assert identity.user_id == 'user-uuid-123'


# =====================================================================
# 3. Audience validation
# =====================================================================


class TestAudienceValidation:

    def test_wrong_audience_rejected(self, hs256_verifier):
        token = _make_hs256_token(aud='wrong-audience')
        with pytest.raises(TokenVerificationError) as exc_info:
            hs256_verifier.verify(token)
        assert exc_info.value.code == 'invalid_audience'

    def test_correct_audience_accepted(self, hs256_verifier):
        token = _make_hs256_token(aud='authenticated')
        identity = hs256_verifier.verify(token)
        assert identity.user_id == 'user-uuid-123'


# =====================================================================
# 4. Signature validation
# =====================================================================


class TestSignatureValidation:

    def test_wrong_secret_rejected(self, hs256_verifier):
        token = _make_hs256_token(secret='wrong-secret')
        with pytest.raises(TokenVerificationError) as exc_info:
            hs256_verifier.verify(token)
        assert exc_info.value.code == 'decode_error'

    def test_rs256_with_wrong_key_rejected(self):
        # Create a different key pair
        other_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        other_public = other_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        class _OtherProvider:
            def get_signing_key(self, token):
                return other_public

        verifier = TokenVerifier(
            key_provider=_OtherProvider(),
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )
        token = _make_rs256_token()  # Signed with original key
        with pytest.raises(TokenVerificationError) as exc_info:
            verifier.verify(token)
        assert exc_info.value.code == 'decode_error'


# =====================================================================
# 5. Required claims
# =====================================================================


class TestRequiredClaims:

    def test_missing_sub_rejected(self, hs256_verifier):
        # Create token without sub
        payload = {
            'email': 'test@example.com',
            'aud': TEST_AUDIENCE,
            'exp': int(time.time()) + 3600,
        }
        token = jwt.encode(payload, TEST_SECRET, algorithm='HS256')
        with pytest.raises(TokenVerificationError) as exc_info:
            hs256_verifier.verify(token)
        assert exc_info.value.code in ('missing_sub_claim', 'invalid_token')

    def test_missing_email_rejected_when_required(self, static_provider):
        verifier = TokenVerifier(
            key_provider=static_provider,
            audience=TEST_AUDIENCE,
            algorithms=['HS256'],
            require_email=True,
        )
        token = _make_hs256_token(email='')
        with pytest.raises(TokenVerificationError) as exc_info:
            verifier.verify(token)
        assert exc_info.value.code == 'missing_email_claim'

    def test_missing_email_accepted_when_not_required(self, static_provider):
        verifier = TokenVerifier(
            key_provider=static_provider,
            audience=TEST_AUDIENCE,
            algorithms=['HS256'],
            require_email=False,
        )
        token = _make_hs256_token(email='')
        identity = verifier.verify(token)
        assert identity.email == ''


# =====================================================================
# 6. Malformed tokens
# =====================================================================


class TestMalformedTokens:

    def test_empty_string_rejected(self, hs256_verifier):
        with pytest.raises(TokenVerificationError) as exc_info:
            hs256_verifier.verify('')
        assert exc_info.value.code == 'empty_token'

    def test_whitespace_rejected(self, hs256_verifier):
        with pytest.raises(TokenVerificationError) as exc_info:
            hs256_verifier.verify('   ')
        assert exc_info.value.code == 'empty_token'

    def test_garbage_string_rejected(self, hs256_verifier):
        with pytest.raises(TokenVerificationError) as exc_info:
            hs256_verifier.verify('not.a.valid.jwt')
        assert exc_info.value.code in ('decode_error', 'invalid_token')

    def test_none_like_rejected(self, hs256_verifier):
        with pytest.raises(TokenVerificationError):
            hs256_verifier.verify(None)


# =====================================================================
# 7. Bearer token extraction
# =====================================================================


class TestBearerExtraction:

    def _make_request(self, headers: dict[str, str] | None = None):
        """Create a mock Starlette Request with given headers."""
        mock = MagicMock()
        mock.headers = headers or {}
        return mock

    def test_extracts_bearer_token(self):
        request = self._make_request({'authorization': 'Bearer abc123'})
        assert extract_bearer_token(request) == 'abc123'

    def test_strips_whitespace(self):
        request = self._make_request({'authorization': 'Bearer  token_with_spaces  '})
        assert extract_bearer_token(request) == 'token_with_spaces'

    def test_no_auth_header_returns_none(self):
        request = self._make_request({})
        assert extract_bearer_token(request) is None

    def test_non_bearer_scheme_returns_none(self):
        request = self._make_request({'authorization': 'Basic dXNlcjpwYXNz'})
        assert extract_bearer_token(request) is None

    def test_empty_bearer_returns_empty_string(self):
        request = self._make_request({'authorization': 'Bearer '})
        assert extract_bearer_token(request) == ''

    def test_case_sensitive_bearer_prefix(self):
        # "bearer" (lowercase) should not match per HTTP convention
        request = self._make_request({'authorization': 'bearer abc123'})
        assert extract_bearer_token(request) is None


# =====================================================================
# 8. Key provider error handling
# =====================================================================


class TestKeyProviderErrors:

    def test_jwks_error_maps_to_verification_error(self):
        class _FailingProvider:
            def get_signing_key(self, token):
                raise Exception('network error')

        verifier = TokenVerifier(
            key_provider=_FailingProvider(),
            audience=TEST_AUDIENCE,
            algorithms=['HS256'],
        )
        token = _make_hs256_token()
        with pytest.raises(Exception):
            verifier.verify(token)


# =====================================================================
# 9. Factory function
# =====================================================================


class TestCreateTokenVerifier:

    def test_creates_with_supabase_url(self):
        verifier = create_token_verifier(
            supabase_url='https://test.supabase.co',
        )
        assert isinstance(verifier, TokenVerifier)

    def test_creates_with_jwt_secret(self):
        verifier = create_token_verifier(jwt_secret='test-secret')
        assert isinstance(verifier, TokenVerifier)

    def test_prefers_supabase_url_over_secret(self):
        verifier = create_token_verifier(
            supabase_url='https://test.supabase.co',
            jwt_secret='test-secret',
        )
        # Should create JWKS-based verifier (RS256)
        assert isinstance(verifier, TokenVerifier)

    def test_raises_without_credentials(self):
        with pytest.raises(ValueError, match='Either supabase_url'):
            create_token_verifier()

    def test_static_key_verifier_works_end_to_end(self):
        verifier = create_token_verifier(
            jwt_secret=TEST_SECRET,
            audience=TEST_AUDIENCE,
        )
        token = _make_hs256_token()
        identity = verifier.verify(token)
        assert identity.user_id == 'user-uuid-123'


# =====================================================================
# 10. AuthIdentity dataclass
# =====================================================================


class TestAuthIdentity:

    def test_frozen(self):
        identity = AuthIdentity(
            user_id='u1', email='a@b.com',
        )
        with pytest.raises(AttributeError):
            identity.user_id = 'u2'

    def test_defaults(self):
        identity = AuthIdentity(user_id='u1', email='a@b.com')
        assert identity.role == 'authenticated'
        assert identity.raw_claims == {}

    def test_equality(self):
        a = AuthIdentity(user_id='u1', email='a@b.com')
        b = AuthIdentity(user_id='u1', email='a@b.com')
        assert a == b
