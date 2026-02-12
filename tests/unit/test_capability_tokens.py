"""Unit tests for capability token primitives (bd-1pwb.10.1).

Tests:
- CapabilityToken validation and claims structure
- CapabilityTokenIssuer signing
- CapabilityTokenValidator verification and operation scoping
- JTIReplayStore eviction and stats
"""

import pytest
import time
from unittest.mock import patch

from boring_ui.api.capability_tokens import (
    CapabilityToken,
    CapabilityTokenIssuer,
    CapabilityTokenValidator,
    JTIReplayStore,
)

# Generate RSA key pair for testing
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


@pytest.fixture(scope="module")
def rsa_keys():
    """Generate RSA key pair for tests."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


# --- CapabilityToken ---

class TestCapabilityToken:
    """CapabilityToken creation and validation."""

    def test_valid_token(self):
        tok = CapabilityToken(
            workspace_id="ws-1",
            operations={"files:read"},
            ttl_seconds=60,
        )
        assert tok.workspace_id == "ws-1"
        assert tok.operations == {"files:read"}
        assert tok.ttl_seconds == 60
        assert len(tok.jti) > 0

    def test_unique_jti(self):
        t1 = CapabilityToken(workspace_id="ws", operations={"x"})
        t2 = CapabilityToken(workspace_id="ws", operations={"x"})
        assert t1.jti != t2.jti

    def test_ttl_too_low_raises(self):
        with pytest.raises(ValueError, match="TTL"):
            CapabilityToken(workspace_id="ws", operations={"x"}, ttl_seconds=2)

    def test_ttl_too_high_raises(self):
        with pytest.raises(ValueError, match="TTL"):
            CapabilityToken(workspace_id="ws", operations={"x"}, ttl_seconds=7200)

    def test_empty_operations_raises(self):
        with pytest.raises(ValueError, match="Operations"):
            CapabilityToken(workspace_id="ws", operations=set())

    def test_non_string_operations_raises(self):
        with pytest.raises(ValueError, match="operations must be strings"):
            CapabilityToken(workspace_id="ws", operations={123})

    def test_to_claims_structure(self):
        tok = CapabilityToken(workspace_id="ws-1", operations={"files:read", "git:status"})
        claims = tok.to_claims()
        assert claims["iss"] == "boring-ui/hosted"
        assert claims["aud"] == "sandbox"
        assert claims["sub"] == "control-plane"
        assert claims["workspace_id"] == "ws-1"
        assert set(claims["ops"]) == {"files:read", "git:status"}
        assert claims["jti"] == tok.jti
        assert "iat" in claims
        assert "exp" in claims
        assert claims["exp"] > claims["iat"]

    def test_to_claims_ops_sorted(self):
        tok = CapabilityToken(workspace_id="ws", operations={"z:op", "a:op", "m:op"})
        claims = tok.to_claims()
        assert claims["ops"] == ["a:op", "m:op", "z:op"]


# --- CapabilityTokenIssuer ---

class TestCapabilityTokenIssuer:
    """CapabilityTokenIssuer signing."""

    def test_issue_token_returns_jwt(self, rsa_keys):
        private_pem, _ = rsa_keys
        issuer = CapabilityTokenIssuer(private_pem)
        token = issuer.issue_token("ws-1", {"files:read"})
        assert isinstance(token, str)
        assert len(token) > 0
        # JWT has 3 parts
        assert token.count(".") == 2

    def test_issue_token_custom_ttl(self, rsa_keys):
        private_pem, _ = rsa_keys
        issuer = CapabilityTokenIssuer(private_pem)
        token = issuer.issue_token("ws-1", {"files:read"}, ttl_seconds=120)
        assert isinstance(token, str)

    def test_different_operations_produce_different_tokens(self, rsa_keys):
        private_pem, _ = rsa_keys
        issuer = CapabilityTokenIssuer(private_pem)
        t1 = issuer.issue_token("ws-1", {"files:read"})
        t2 = issuer.issue_token("ws-1", {"exec:run"})
        assert t1 != t2


# --- CapabilityTokenValidator ---

class TestCapabilityTokenValidator:
    """CapabilityTokenValidator verification."""

    def test_validates_good_token(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        issuer = CapabilityTokenIssuer(private_pem)
        validator = CapabilityTokenValidator(public_pem)

        token = issuer.issue_token("ws-1", {"files:read"})
        claims = validator.validate_token(token)

        assert claims is not None
        assert claims["workspace_id"] == "ws-1"
        assert "files:read" in claims["ops"]
        assert claims["jti"] is not None

    def test_rejects_expired_token(self, rsa_keys):
        private_pem, public_pem = rsa_keys
        issuer = CapabilityTokenIssuer(private_pem)
        validator = CapabilityTokenValidator(public_pem)

        # Issue token with minimum TTL then wait
        token = issuer.issue_token("ws-1", {"files:read"}, ttl_seconds=5)

        # Mock time to be past expiry
        import jwt as pyjwt
        with patch("jwt.decode", side_effect=pyjwt.ExpiredSignatureError("expired")):
            claims = validator.validate_token(token)
            assert claims is None

    def test_rejects_wrong_key(self, rsa_keys):
        private_pem, _ = rsa_keys
        issuer = CapabilityTokenIssuer(private_pem)

        # Generate a different key pair
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_public = other_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        validator = CapabilityTokenValidator(other_public)
        token = issuer.issue_token("ws-1", {"files:read"})
        claims = validator.validate_token(token)
        assert claims is None

    def test_rejects_garbage_token(self, rsa_keys):
        _, public_pem = rsa_keys
        validator = CapabilityTokenValidator(public_pem)
        assert validator.validate_token("not.a.jwt") is None
        assert validator.validate_token("") is None
        assert validator.validate_token("garbage") is None

    def test_validate_operation_exact_match(self):
        claims = {"ops": ["files:read", "git:status"]}
        # Use a validator just for validate_operation (doesn't need real key)
        validator = CapabilityTokenValidator.__new__(CapabilityTokenValidator)
        assert validator.validate_operation(claims, "files:read") is True
        assert validator.validate_operation(claims, "git:status") is True
        assert validator.validate_operation(claims, "exec:run") is False

    def test_validate_operation_wildcard(self):
        validator = CapabilityTokenValidator.__new__(CapabilityTokenValidator)
        claims = {"ops": ["*"]}
        assert validator.validate_operation(claims, "anything") is True

    def test_validate_operation_namespace_wildcard(self):
        validator = CapabilityTokenValidator.__new__(CapabilityTokenValidator)
        claims = {"ops": ["files:*"]}
        assert validator.validate_operation(claims, "files:read") is True
        assert validator.validate_operation(claims, "files:write") is True
        assert validator.validate_operation(claims, "git:status") is False


# --- JTIReplayStore ---

class TestJTIReplayStore:
    """JTIReplayStore tracking and eviction."""

    def test_new_jti_not_replayed(self):
        store = JTIReplayStore()
        assert store.is_replayed("new-jti") is False

    def test_recorded_jti_is_replayed(self):
        store = JTIReplayStore()
        store.record_jti("jti-1", ttl_seconds=60)
        assert store.is_replayed("jti-1") is True

    def test_expired_jti_is_not_replayed(self):
        store = JTIReplayStore()
        # Record with very short TTL
        store.record_jti("jti-1", ttl_seconds=1)
        # Simulate time passing
        store._cache["jti-1"] = time.time() - 10  # Expired
        assert store.is_replayed("jti-1") is False

    def test_max_size_eviction(self):
        store = JTIReplayStore(max_size=3)
        store.record_jti("a", 60)
        store.record_jti("b", 60)
        store.record_jti("c", 60)
        store.record_jti("d", 60)  # Should evict "a"
        assert "a" not in store._cache
        assert "d" in store._cache

    def test_stats_tracking(self):
        store = JTIReplayStore()
        store.record_jti("x", 60)

        store.is_replayed("x")  # Hit
        store.is_replayed("y")  # Miss
        store.is_replayed("y")  # Miss

        stats = store.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["total"] == 3
        assert stats["hit_rate"] == pytest.approx(1 / 3)

    def test_initial_stats(self):
        store = JTIReplayStore()
        stats = store.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["cached_jtis"] == 0

    def test_multiple_replay_attempts(self):
        store = JTIReplayStore()
        store.record_jti("x", 60)
        assert store.is_replayed("x") is True
        assert store.is_replayed("x") is True  # Still replayed
        assert store.stats["hits"] == 2
