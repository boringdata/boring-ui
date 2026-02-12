"""Tests for ServiceTokenSigner (RS256 service-to-service auth)."""

import time
import pytest

from boring_ui.api.auth import ServiceTokenSigner


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

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    return {"private": private_pem}


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

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    return {"private": private_pem}


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
