"""Tests for service-to-service authentication and key rotation."""

import json
import time
import pytest
from unittest.mock import patch

from .service_auth import (
    ServiceIdentity,
    ServiceTokenSigner,
    ServiceTokenValidator,
)


@pytest.fixture
def rsa_keys():
    """Generate RSA key pair for testing."""
    import cryptography.hazmat.primitives.asymmetric.rsa as rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    return {"private": private_pem, "public": public_pem}


@pytest.fixture
def rsa_keys_v2():
    """Generate second RSA key pair for rotation testing."""
    import cryptography.hazmat.primitives.asymmetric.rsa as rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    return {"private": private_pem, "public": public_pem}


class TestServiceIdentity:
    """Tests for ServiceIdentity data structure."""

    def test_service_identity_creation(self):
        """ServiceIdentity should be created with proper fields."""
        identity = ServiceIdentity(
            service_name="hosted-api",
            issued_at=100,
            expires_at=200,
            key_version=1,
        )

        assert identity.service_name == "hosted-api"
        assert identity.issued_at == 100
        assert identity.expires_at == 200
        assert identity.key_version == 1

    def test_to_claims(self):
        """ServiceIdentity should convert to JWT claims."""
        identity = ServiceIdentity(
            service_name="sandbox-api",
            issued_at=100,
            expires_at=200,
            key_version=2,
        )

        claims = identity.to_claims()

        assert claims["iss"] == "boring-ui"
        assert claims["sub"] == "sandbox-api"
        assert claims["iat"] == 100
        assert claims["exp"] == 200
        assert claims["key_version"] == 2


class TestServiceTokenSigner:
    """Tests for service token signing."""

    def test_sign_request(self, rsa_keys):
        """ServiceTokenSigner should sign valid tokens."""
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")

        token = signer.sign_request(ttl_seconds=60)

        assert isinstance(token, str)
        assert len(token) > 0
        # JWT has three parts separated by dots
        assert token.count(".") == 2

    def test_sign_request_ttl(self, rsa_keys):
        """Signed token should have correct TTL."""
        import jwt

        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        token = signer.sign_request(ttl_seconds=120)

        # Decode without verification to check claims
        claims = jwt.decode(token, options={"verify_signature": False})

        assert claims["exp"] - claims["iat"] == 120

    def test_key_version_in_token(self, rsa_keys):
        """Signed token should include key version in header."""
        import jwt

        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        token = signer.sign_request()

        header = jwt.get_unverified_header(token)

        assert header["kid"] == "service-v1"
        assert header["service"] == "hosted-api"

    def test_rotate_key(self, rsa_keys, rsa_keys_v2):
        """ServiceTokenSigner should support key rotation."""
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")

        assert signer.current_key_version == 1

        new_version = signer.rotate_key(rsa_keys_v2["private"])

        assert new_version == 2
        assert signer.current_key_version == 2

        # New tokens should have new key version
        import jwt

        token = signer.sign_request()
        header = jwt.get_unverified_header(token)
        assert header["kid"] == "service-v2"

    def test_multiple_rotations(self, rsa_keys, rsa_keys_v2):
        """ServiceTokenSigner should handle multiple rotations."""
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")

        signer.rotate_key(rsa_keys_v2["private"])
        assert signer.current_key_version == 2

        signer.rotate_key(rsa_keys["private"])
        assert signer.current_key_version == 3


class TestServiceTokenValidator:
    """Tests for service token validation."""

    def test_validate_token_success(self, rsa_keys):
        """ServiceTokenValidator should validate correct tokens."""
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        validator = ServiceTokenValidator({1: rsa_keys["public"]}, current_version=1)

        token = signer.sign_request()
        claims = validator.validate_token(token)

        assert claims is not None
        assert claims["sub"] == "hosted-api"

    def test_validate_token_wrong_key(self, rsa_keys, rsa_keys_v2):
        """ServiceTokenValidator should reject tokens signed with wrong key."""
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        validator = ServiceTokenValidator(
            {1: rsa_keys_v2["public"]}, current_version=1
        )

        token = signer.sign_request()
        claims = validator.validate_token(token)

        assert claims is None

    def test_validate_expired_token(self, rsa_keys):
        """ServiceTokenValidator should reject expired tokens."""
        import jwt as pyjwt

        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        validator = ServiceTokenValidator({1: rsa_keys["public"]}, current_version=1)

        token = signer.sign_request(ttl_seconds=1)

        # Wait for expiry
        time.sleep(1.1)

        claims = validator.validate_token(token)

        assert claims is None

    def test_validate_token_unknown_version(self, rsa_keys):
        """ServiceTokenValidator should reject tokens from unknown key versions."""
        import jwt as pyjwt

        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        token = signer.sign_request()

        # Validator only has version 2, not version 1
        validator = ServiceTokenValidator({2: rsa_keys["public"]}, current_version=2)

        claims = validator.validate_token(token)

        assert claims is None

    def test_validate_token_during_rotation(self, rsa_keys, rsa_keys_v2):
        """ServiceTokenValidator should accept old keys during grace period."""
        signer_v1 = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        token_v1 = signer_v1.sign_request()

        # Validator has both v1 and v2, current is v2 (rotation happened)
        validator = ServiceTokenValidator(
            {1: rsa_keys["public"], 2: rsa_keys_v2["public"]},
            current_version=2,
            grace_period_seconds=300,
        )

        # Old token should be accepted during grace period
        claims = validator.validate_token(token_v1)

        assert claims is not None
        assert claims["key_version"] == 1

    def test_validate_token_reject_future_version(self, rsa_keys, rsa_keys_v2):
        """ServiceTokenValidator should reject tokens from future key versions."""
        signer_v2 = ServiceTokenSigner(rsa_keys_v2["private"], "hosted-api")

        # Manually sign with version 2
        import jwt as pyjwt

        now = int(time.time())
        claims = {
            "iss": "boring-ui",
            "sub": "hosted-api",
            "iat": now,
            "exp": now + 60,
            "key_version": 2,
        }
        token = pyjwt.encode(
            claims,
            rsa_keys_v2["private"],
            algorithm="RS256",
            headers={"typ": "JWT", "kid": "service-v2"},
        )

        # Validator only has v1, current is v1
        validator = ServiceTokenValidator({1: rsa_keys["public"]}, current_version=1)

        # Future version should be rejected
        claims = validator.validate_token(token)

        assert claims is None

    def test_validate_service_name_filter(self, rsa_keys):
        """ServiceTokenValidator should filter by accepted service names."""
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        validator = ServiceTokenValidator({1: rsa_keys["public"]}, current_version=1)

        token = signer.sign_request()

        # Accept only sandbox-api (hosted-api should be rejected)
        claims = validator.validate_token(token, accepted_services=["sandbox-api"])

        assert claims is None

    def test_validate_service_name_empty_list(self, rsa_keys):
        """ServiceTokenValidator should reject all services with empty allowlist."""
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        validator = ServiceTokenValidator({1: rsa_keys["public"]}, current_version=1)

        token = signer.sign_request()

        # Empty list should reject all services (not disable filtering)
        claims = validator.validate_token(token, accepted_services=[])

        assert claims is None

    def test_validate_service_name_allowed(self, rsa_keys):
        """ServiceTokenValidator should allow matching service names."""
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        validator = ServiceTokenValidator({1: rsa_keys["public"]}, current_version=1)

        token = signer.sign_request()

        # Accept hosted-api
        claims = validator.validate_token(
            token, accepted_services=["hosted-api", "sandbox-api"]
        )

        assert claims is not None

    def test_validator_stats(self, rsa_keys):
        """ServiceTokenValidator should track validation statistics."""
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        validator = ServiceTokenValidator({1: rsa_keys["public"]}, current_version=1)

        token = signer.sign_request()

        # Valid tokens
        validator.validate_token(token)
        validator.validate_token(token)

        # Invalid tokens
        validator.validate_token("invalid.token.here")

        stats = validator.stats

        assert stats["attempts"] == 3
        assert stats["successes"] == 2
        assert stats["success_rate"] == pytest.approx(2 / 3)

    def test_add_key_version(self, rsa_keys, rsa_keys_v2):
        """ServiceTokenValidator should support adding key versions."""
        validator = ServiceTokenValidator({1: rsa_keys["public"]}, current_version=1)

        validator.add_key_version(2, rsa_keys_v2["public"])

        assert 2 in validator.key_versions
        assert validator.current_version == 2

    def test_retire_key_version(self, rsa_keys, rsa_keys_v2):
        """ServiceTokenValidator should support retiring key versions."""
        validator = ServiceTokenValidator(
            {1: rsa_keys["public"], 2: rsa_keys_v2["public"]}, current_version=2
        )

        result = validator.retire_key_version(1)

        assert result is True
        # Key is retained in key_versions for grace period validation
        assert 1 in validator.key_versions
        assert 1 in validator._key_retirement_times

    def test_retire_nonexistent_key(self, rsa_keys):
        """ServiceTokenValidator should handle retiring nonexistent keys."""
        validator = ServiceTokenValidator({1: rsa_keys["public"]}, current_version=1)

        result = validator.retire_key_version(99)

        assert result is False

    def test_from_env(self, rsa_keys, monkeypatch):
        """ServiceTokenValidator should be created from env vars."""
        key_versions_json = json.dumps({1: rsa_keys["public"]})

        monkeypatch.setenv("SERVICE_KEY_VERSIONS", key_versions_json)
        monkeypatch.setenv("SERVICE_CURRENT_VERSION", "1")
        monkeypatch.setenv("SERVICE_KEY_ROTATION_GRACE_SECONDS", "600")

        validator = ServiceTokenValidator.from_env()

        assert validator is not None
        assert 1 in validator.key_versions
        assert validator.current_version == 1
        assert validator.grace_period_seconds == 600

    def test_from_env_missing(self, monkeypatch):
        """ServiceTokenValidator.from_env should return None if env vars missing."""
        monkeypatch.delenv("SERVICE_KEY_VERSIONS", raising=False)

        validator = ServiceTokenValidator.from_env()

        assert validator is None

    def test_from_env_invalid_json(self, monkeypatch):
        """ServiceTokenValidator.from_env should handle invalid JSON."""
        monkeypatch.setenv("SERVICE_KEY_VERSIONS", "not-valid-json")

        validator = ServiceTokenValidator.from_env()

        assert validator is None

    def test_from_env_invalid_current_version(self, rsa_keys, monkeypatch):
        """ServiceTokenValidator.from_env should handle invalid current_version."""
        key_versions_json = json.dumps({1: rsa_keys["public"]})
        monkeypatch.setenv("SERVICE_KEY_VERSIONS", key_versions_json)
        monkeypatch.setenv("SERVICE_CURRENT_VERSION", "not-a-number")

        validator = ServiceTokenValidator.from_env()

        assert validator is None

    def test_from_env_invalid_grace_period(self, rsa_keys, monkeypatch):
        """ServiceTokenValidator.from_env should handle invalid grace_period."""
        key_versions_json = json.dumps({1: rsa_keys["public"]})
        monkeypatch.setenv("SERVICE_KEY_VERSIONS", key_versions_json)
        monkeypatch.setenv("SERVICE_KEY_ROTATION_GRACE_SECONDS", "not-a-number")

        validator = ServiceTokenValidator.from_env()

        assert validator is None

    def test_grace_period_enforcement(self, rsa_keys, rsa_keys_v2):
        """ServiceTokenValidator should enforce grace period after key retirement."""
        signer_v1 = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        token_v1 = signer_v1.sign_request(ttl_seconds=120)

        # Validator with both v1 and v2, current is v2
        validator = ServiceTokenValidator(
            {1: rsa_keys["public"], 2: rsa_keys_v2["public"]},
            current_version=2,
            grace_period_seconds=1,  # Very short grace period
        )

        # Token should be accepted before retirement
        assert validator.validate_token(token_v1) is not None

        # Retire v1
        validator.retire_key_version(1)

        # Token should still be accepted during grace period
        assert validator.validate_token(token_v1) is not None

        # Wait for grace period to expire
        time.sleep(1.1)

        # Token should be rejected after grace period
        assert validator.validate_token(token_v1) is None


class TestKeyRotationWorkflow:
    """Integration tests for key rotation workflow."""

    def test_rotation_workflow(self, rsa_keys, rsa_keys_v2):
        """Test complete key rotation workflow."""
        # Initial setup with v1, short grace period for testing
        signer = ServiceTokenSigner(rsa_keys["private"], "hosted-api")
        validator = ServiceTokenValidator(
            {1: rsa_keys["public"]}, current_version=1, grace_period_seconds=1
        )

        token_v1 = signer.sign_request(ttl_seconds=120)
        assert validator.validate_token(token_v1) is not None

        # Rotation: add v2 to validator, rotate signer
        validator.add_key_version(2, rsa_keys_v2["public"])
        signer.rotate_key(rsa_keys_v2["private"])

        # New tokens should use v2
        token_v2 = signer.sign_request()
        assert validator.validate_token(token_v2) is not None

        # Old tokens should still work during grace period
        assert validator.validate_token(token_v1) is not None

        # Retire v1
        validator.retire_key_version(1)

        # New tokens work
        assert validator.validate_token(token_v2) is not None

        # Old tokens still work during grace period
        assert validator.validate_token(token_v1) is not None

        # Wait for grace period to expire
        time.sleep(1.1)

        # Old tokens fail after grace period
        assert validator.validate_token(token_v1) is None
