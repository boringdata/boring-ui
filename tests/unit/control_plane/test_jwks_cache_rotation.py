"""JWKS cache and key rotation correctness tests.

Bead: bd-223o.7.1.1 (B1a)

Validates key rotation and cache refresh behavior to prevent auth outages
during key rollover windows:
  - Cache TTL constant matches design doc (300s / 5 minutes)
  - Key provider is invoked per verification (no verifier-level caching)
  - Key rotation: old key stops working when provider rotates
  - Rollover window: both old and new keys work when provider returns either
  - Provider failure during rotation maps to TokenVerificationError
  - StaticKeyProvider is rotation-immune (always returns same key)
  - JWKSKeyProvider wraps PyJWKClientError correctly
  - JWKSKeyProvider passes correct cache params to PyJWKClient
  - Sequential verifications with evolving provider state
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClientError

from control_plane.app.security.token_verify import (
    JWKS_CACHE_TTL_SECONDS,
    JWKSKeyProvider,
    StaticKeyProvider,
    TokenVerificationError,
    TokenVerifier,
)


# ── Key generation helpers ───────────────────────────────────────────


def _gen_rsa_keypair():
    """Generate a fresh RSA key pair (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


KEY_A_PRIV, KEY_A_PUB = _gen_rsa_keypair()
KEY_B_PRIV, KEY_B_PUB = _gen_rsa_keypair()

TEST_AUDIENCE = 'authenticated'


def _make_token(private_key, sub='user-1', alg='RS256'):
    """Create a signed JWT with standard claims."""
    payload = {
        'sub': sub,
        'email': f'{sub}@test.com',
        'role': 'authenticated',
        'aud': TEST_AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    return jwt.encode(payload, private_key, algorithm=alg)


# ── Pluggable test providers ────────────────────────────────────────


class RotatingKeyProvider:
    """Key provider that can be rotated to a new key mid-test."""

    def __init__(self, initial_key):
        self.current_key = initial_key
        self.call_count = 0

    def get_signing_key(self, token: str):
        self.call_count += 1
        return self.current_key

    def rotate_to(self, new_key):
        self.current_key = new_key


class FailingKeyProvider:
    """Key provider that fails after N successful calls."""

    def __init__(self, key, fail_after: int = 0):
        self._key = key
        self._fail_after = fail_after
        self._calls = 0

    def get_signing_key(self, token: str):
        self._calls += 1
        if self._calls > self._fail_after:
            raise TokenVerificationError('jwks_fetch_error', 'simulated JWKS outage')
        return self._key


# =====================================================================
# 1. Cache TTL constant
# =====================================================================


class TestCacheTTLConstant:
    """Verify JWKS cache TTL matches the design doc specification."""

    def test_cache_ttl_is_300_seconds(self):
        assert JWKS_CACHE_TTL_SECONDS == 300

    def test_cache_ttl_is_5_minutes(self):
        assert JWKS_CACHE_TTL_SECONDS == 5 * 60


# =====================================================================
# 2. Key provider invoked per verification
# =====================================================================


class TestProviderInvokedPerCall:
    """TokenVerifier calls key_provider.get_signing_key on every verify()."""

    def test_provider_called_each_time(self):
        provider = RotatingKeyProvider(KEY_A_PUB)
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )
        token = _make_token(KEY_A_PRIV)
        verifier.verify(token)
        verifier.verify(token)
        verifier.verify(token)
        assert provider.call_count == 3

    def test_provider_called_even_for_same_token(self):
        """No token-level caching in the verifier itself."""
        provider = RotatingKeyProvider(KEY_A_PUB)
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )
        token = _make_token(KEY_A_PRIV)
        for _ in range(5):
            verifier.verify(token)
        assert provider.call_count == 5


# =====================================================================
# 3. Key rotation: old key stops working
# =====================================================================


class TestKeyRotation:
    """When provider rotates keys, old tokens fail with new key."""

    def test_token_signed_with_old_key_fails_after_rotation(self):
        provider = RotatingKeyProvider(KEY_A_PUB)
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )

        token_a = _make_token(KEY_A_PRIV, sub='user-a')
        # Verify succeeds with key A.
        identity = verifier.verify(token_a)
        assert identity.user_id == 'user-a'

        # Rotate to key B.
        provider.rotate_to(KEY_B_PUB)

        # Old token signed with key A now fails.
        with pytest.raises(TokenVerificationError) as exc_info:
            verifier.verify(token_a)
        assert exc_info.value.code == 'decode_error'

    def test_new_token_works_after_rotation(self):
        provider = RotatingKeyProvider(KEY_A_PUB)
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )

        # Rotate to key B.
        provider.rotate_to(KEY_B_PUB)

        # Token signed with key B works.
        token_b = _make_token(KEY_B_PRIV, sub='user-b')
        identity = verifier.verify(token_b)
        assert identity.user_id == 'user-b'


# =====================================================================
# 4. Rollover window: both keys work
# =====================================================================


class TestRolloverWindow:
    """During key rollover, a provider that checks both keys allows both."""

    def test_both_keys_valid_during_rollover(self):
        """Simulate a JWKS endpoint that returns both old and new keys."""

        class DualKeyProvider:
            """Returns whichever key matches the token signature."""

            def get_signing_key(self, token: str):
                # Try key A first; if it doesn't match header kid, try B.
                # In real JWKS, PyJWKClient matches by kid.
                # Here we try both and return whichever validates.
                for key in (KEY_A_PUB, KEY_B_PUB):
                    try:
                        jwt.decode(
                            token, key, algorithms=['RS256'],
                            audience=TEST_AUDIENCE,
                            options={'verify_exp': False},
                        )
                        return key
                    except jwt.InvalidSignatureError:
                        continue
                # Default to A (will fail validation in verifier).
                return KEY_A_PUB

        provider = DualKeyProvider()
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )

        token_a = _make_token(KEY_A_PRIV, sub='user-a')
        token_b = _make_token(KEY_B_PRIV, sub='user-b')

        assert verifier.verify(token_a).user_id == 'user-a'
        assert verifier.verify(token_b).user_id == 'user-b'

    def test_old_key_removed_after_rollover_complete(self):
        """After rollover, only new key works."""
        provider = RotatingKeyProvider(KEY_A_PUB)
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )

        token_a = _make_token(KEY_A_PRIV)
        verifier.verify(token_a)  # works

        # Complete rotation to B.
        provider.rotate_to(KEY_B_PUB)

        # A no longer valid.
        with pytest.raises(TokenVerificationError):
            verifier.verify(token_a)

        # B now valid.
        token_b = _make_token(KEY_B_PRIV)
        verifier.verify(token_b)


# =====================================================================
# 5. Provider failure during rotation
# =====================================================================


class TestProviderFailureDuringRotation:
    """JWKS fetch failures during rotation are surfaced correctly."""

    def test_first_call_succeeds_second_fails(self):
        provider = FailingKeyProvider(KEY_A_PUB, fail_after=1)
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )
        token = _make_token(KEY_A_PRIV)

        # First call succeeds.
        verifier.verify(token)

        # Second call fails with jwks_fetch_error.
        with pytest.raises(TokenVerificationError) as exc_info:
            verifier.verify(token)
        assert exc_info.value.code == 'jwks_fetch_error'

    def test_provider_failure_preserves_error_detail(self):
        provider = FailingKeyProvider(KEY_A_PUB, fail_after=0)
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )
        token = _make_token(KEY_A_PRIV)
        with pytest.raises(TokenVerificationError) as exc_info:
            verifier.verify(token)
        assert 'simulated JWKS outage' in exc_info.value.detail


# =====================================================================
# 6. StaticKeyProvider is rotation-immune
# =====================================================================


class TestStaticKeyProviderStability:
    """StaticKeyProvider always returns the same key regardless of calls."""

    def test_returns_same_key_every_time(self):
        provider = StaticKeyProvider('my-secret')
        results = [provider.get_signing_key(f'token_{i}') for i in range(10)]
        assert all(r == 'my-secret' for r in results)

    def test_static_provider_hs256_survives_multiple_verifications(self):
        provider = StaticKeyProvider('test-secret')
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['HS256'],
        )
        for i in range(5):
            payload = {
                'sub': f'user-{i}',
                'email': f'u{i}@test.com',
                'aud': TEST_AUDIENCE,
                'exp': int(time.time()) + 3600,
            }
            token = jwt.encode(payload, 'test-secret', algorithm='HS256')
            identity = verifier.verify(token)
            assert identity.user_id == f'user-{i}'


# =====================================================================
# 7. JWKSKeyProvider error wrapping
# =====================================================================


class TestJWKSKeyProviderErrors:
    """JWKSKeyProvider wraps PyJWKClientError into TokenVerificationError."""

    @patch('control_plane.app.security.token_verify.PyJWKClient')
    def test_pyjwkclient_error_wrapped(self, mock_client_cls):
        mock_instance = MagicMock()
        mock_instance.get_signing_key_from_jwt.side_effect = PyJWKClientError(
            'Unable to find a signing key'
        )
        mock_client_cls.return_value = mock_instance

        provider = JWKSKeyProvider('https://example.com/.well-known/jwks.json')
        with pytest.raises(TokenVerificationError) as exc_info:
            provider.get_signing_key('some.jwt.token')
        assert exc_info.value.code == 'jwks_fetch_error'
        assert 'signing key' in exc_info.value.detail

    @patch('control_plane.app.security.token_verify.PyJWKClient')
    def test_pyjwkclient_success_returns_key(self, mock_client_cls):
        mock_signing_key = MagicMock()
        mock_signing_key.key = 'the-resolved-key'
        mock_instance = MagicMock()
        mock_instance.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_client_cls.return_value = mock_instance

        provider = JWKSKeyProvider('https://example.com/.well-known/jwks.json')
        result = provider.get_signing_key('some.jwt.token')
        assert result == 'the-resolved-key'


# =====================================================================
# 8. JWKSKeyProvider constructor configuration
# =====================================================================


class TestJWKSKeyProviderConfig:
    """JWKSKeyProvider passes correct params to PyJWKClient."""

    @patch('control_plane.app.security.token_verify.PyJWKClient')
    def test_default_cache_ttl(self, mock_client_cls):
        JWKSKeyProvider('https://example.com/jwks')
        mock_client_cls.assert_called_once_with(
            'https://example.com/jwks',
            cache_jwk_set=True,
            lifespan=300,
        )

    @patch('control_plane.app.security.token_verify.PyJWKClient')
    def test_custom_cache_ttl(self, mock_client_cls):
        JWKSKeyProvider('https://example.com/jwks', cache_ttl=60)
        mock_client_cls.assert_called_once_with(
            'https://example.com/jwks',
            cache_jwk_set=True,
            lifespan=60,
        )

    @patch('control_plane.app.security.token_verify.PyJWKClient')
    def test_caching_enabled(self, mock_client_cls):
        JWKSKeyProvider('https://example.com/jwks')
        _, kwargs = mock_client_cls.call_args
        assert kwargs['cache_jwk_set'] is True


# =====================================================================
# 9. Sequential verifications with evolving state
# =====================================================================


class TestSequentialVerifications:
    """Multiple sequential verifications track provider state correctly."""

    def test_interleaved_tokens_from_different_keys(self):
        """Verify tokens signed by different keys in alternation."""

        class AlternatingProvider:
            def __init__(self):
                self._call = 0

            def get_signing_key(self, token: str):
                self._call += 1
                # Even calls: key A, Odd calls: key B.
                return KEY_A_PUB if self._call % 2 == 0 else KEY_B_PUB

        provider = AlternatingProvider()
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )

        token_b = _make_token(KEY_B_PRIV, sub='b-user')
        token_a = _make_token(KEY_A_PRIV, sub='a-user')

        # Call 1 (odd) → key B → token_b should work.
        identity1 = verifier.verify(token_b)
        assert identity1.user_id == 'b-user'

        # Call 2 (even) → key A → token_a should work.
        identity2 = verifier.verify(token_a)
        assert identity2.user_id == 'a-user'

    def test_provider_state_not_cached_by_verifier(self):
        """Verifier delegates entirely to provider — no stale key caching."""
        provider = RotatingKeyProvider(KEY_A_PUB)
        verifier = TokenVerifier(
            key_provider=provider,
            audience=TEST_AUDIENCE,
            algorithms=['RS256'],
        )

        # Verify with key A.
        token_a = _make_token(KEY_A_PRIV)
        verifier.verify(token_a)

        # Rotate.
        provider.rotate_to(KEY_B_PUB)

        # Immediately use key B — no stale cache at verifier level.
        token_b = _make_token(KEY_B_PRIV)
        identity = verifier.verify(token_b)
        assert identity.email  # Valid identity returned.


# =====================================================================
# 10. TokenVerificationError structure
# =====================================================================


class TestTokenVerificationErrorStructure:
    """TokenVerificationError carries code and detail for diagnostics."""

    def test_code_and_detail(self):
        err = TokenVerificationError('jwks_fetch_error', 'connection timeout')
        assert err.code == 'jwks_fetch_error'
        assert err.detail == 'connection timeout'
        assert 'jwks_fetch_error' in str(err)
        assert 'connection timeout' in str(err)

    def test_code_only(self):
        err = TokenVerificationError('empty_token')
        assert err.code == 'empty_token'
        assert err.detail == ''
        assert 'empty_token' in str(err)

    def test_inherits_from_exception(self):
        assert issubclass(TokenVerificationError, Exception)
