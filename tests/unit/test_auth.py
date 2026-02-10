"""Tests for ServiceTokenIssuer and capabilities service tokens."""
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from boring_ui.api.auth import ServiceTokenIssuer
from boring_ui.api import create_app


class TestServiceTokenIssuer:
    """Test JWT token issuance and verification."""

    @pytest.fixture
    def issuer(self):
        return ServiceTokenIssuer()

    def test_signing_key_is_256_bits(self, issuer):
        """Signing key should be 256 bits (64 hex chars)."""
        assert len(issuer.signing_key_hex) == 64

    def test_signing_key_unique_per_instance(self):
        """Each issuer should generate a unique signing key."""
        a = ServiceTokenIssuer()
        b = ServiceTokenIssuer()
        assert a.signing_key_hex != b.signing_key_hex

    def test_issue_token_returns_valid_jwt(self, issuer):
        """Issued token should be a valid HS256 JWT."""
        token = issuer.issue_token("sandbox")
        # Should be decodable with the issuer's key
        payload = jwt.decode(
            token, bytes.fromhex(issuer.signing_key_hex), algorithms=["HS256"]
        )
        assert payload["sub"] == "boring-ui"
        assert payload["svc"] == "sandbox"
        assert "iat" in payload
        assert "exp" in payload

    def test_token_default_ttl_one_hour(self, issuer):
        """Default header token should have ~1 hour TTL."""
        token = issuer.issue_token("sandbox")
        payload = jwt.decode(
            token, bytes.fromhex(issuer.signing_key_hex), algorithms=["HS256"]
        )
        ttl = payload["exp"] - payload["iat"]
        assert ttl == 3600

    def test_token_custom_ttl(self, issuer):
        """Token TTL should be configurable."""
        token = issuer.issue_token("sandbox", ttl_seconds=600)
        payload = jwt.decode(
            token, bytes.fromhex(issuer.signing_key_hex), algorithms=["HS256"]
        )
        assert payload["exp"] - payload["iat"] == 600

    def test_query_param_token_short_lived(self, issuer):
        """Query-param token should have 120s TTL."""
        token = issuer.issue_query_param_token("sandbox")
        payload = jwt.decode(
            token, bytes.fromhex(issuer.signing_key_hex), algorithms=["HS256"]
        )
        ttl = payload["exp"] - payload["iat"]
        assert ttl == 120

    def test_header_and_qp_tokens_differ(self, issuer):
        """Header and QP tokens should be different (different TTLs)."""
        header = issuer.issue_token("sandbox")
        qp = issuer.issue_query_param_token("sandbox")
        assert header != qp

    def test_tokens_for_different_services_differ(self, issuer):
        """Tokens for different services should have different svc claims."""
        sandbox = issuer.issue_token("sandbox")
        companion = issuer.issue_token("companion")
        assert sandbox != companion

    # --- Verification ---

    def test_verify_valid_token(self, issuer):
        """Valid token should verify successfully."""
        token = issuer.issue_token("sandbox")
        result = ServiceTokenIssuer.verify_token(
            token, issuer.signing_key_hex, "sandbox"
        )
        assert result is not None
        assert result["svc"] == "sandbox"

    def test_verify_wrong_service_rejected(self, issuer):
        """Token for wrong service should be rejected."""
        token = issuer.issue_token("sandbox")
        result = ServiceTokenIssuer.verify_token(
            token, issuer.signing_key_hex, "companion"
        )
        assert result is None

    def test_verify_empty_key_fail_closed(self, issuer):
        """Empty signing key should reject all tokens (fail-closed)."""
        token = issuer.issue_token("sandbox")
        assert ServiceTokenIssuer.verify_token(token, "", "sandbox") is None

    def test_verify_none_key_fail_closed(self, issuer):
        """None signing key should reject all tokens (fail-closed)."""
        token = issuer.issue_token("sandbox")
        assert ServiceTokenIssuer.verify_token(token, None, "sandbox") is None

    def test_verify_wrong_key_rejected(self, issuer):
        """Token verified with wrong key should be rejected."""
        token = issuer.issue_token("sandbox")
        wrong_key = ServiceTokenIssuer().signing_key_hex  # Different issuer
        result = ServiceTokenIssuer.verify_token(token, wrong_key, "sandbox")
        assert result is None

    def test_verify_tampered_token_rejected(self, issuer):
        """Tampered token should be rejected."""
        token = issuer.issue_token("sandbox")
        tampered = token[:-5] + "XXXXX"
        result = ServiceTokenIssuer.verify_token(
            tampered, issuer.signing_key_hex, "sandbox"
        )
        assert result is None

    def test_verify_garbage_token_rejected(self, issuer):
        """Garbage input should be rejected, not raise."""
        result = ServiceTokenIssuer.verify_token(
            "not.a.jwt", issuer.signing_key_hex, "sandbox"
        )
        assert result is None

    def test_verify_expired_token_rejected(self, issuer):
        """Expired token should be rejected."""
        token = issuer.issue_token("sandbox", ttl_seconds=-1)
        result = ServiceTokenIssuer.verify_token(
            token, issuer.signing_key_hex, "sandbox"
        )
        assert result is None


class TestCapabilitiesServiceTokens:
    """Test service connection info in capabilities endpoint."""

    @pytest.fixture
    def sandbox_client(self):
        """Create a test client with sandbox enabled."""
        app = create_app(include_sandbox=True)
        return TestClient(app)

    @pytest.fixture
    def no_sandbox_client(self):
        """Create a test client without sandbox."""
        app = create_app(include_sandbox=False)
        return TestClient(app)

    def test_no_services_without_sandbox(self, no_sandbox_client):
        """Without sandbox, capabilities should not include services."""
        r = no_sandbox_client.get("/api/capabilities")
        data = r.json()
        assert "services" not in data

    def test_services_with_sandbox(self, sandbox_client):
        """With sandbox, capabilities should include services section."""
        r = sandbox_client.get("/api/capabilities")
        data = r.json()
        assert "services" in data
        assert "sandbox" in data["services"]

    def test_sandbox_service_shape(self, sandbox_client):
        """Sandbox service info should have required fields."""
        r = sandbox_client.get("/api/capabilities")
        svc = r.json()["services"]["sandbox"]
        assert "url" in svc
        assert "token" in svc
        assert "qpToken" in svc
        assert "protocol" in svc
        assert svc["protocol"] == "rest+sse"

    def test_sandbox_url_is_localhost(self, sandbox_client):
        """Sandbox URL should be localhost (not exposed)."""
        r = sandbox_client.get("/api/capabilities")
        url = r.json()["services"]["sandbox"]["url"]
        assert "127.0.0.1" in url

    def test_sandbox_token_is_static_hex(self, sandbox_client):
        """Sandbox token should be a static hex string (not JWT)."""
        r = sandbox_client.get("/api/capabilities")
        token = r.json()["services"]["sandbox"]["token"]
        # Static hex token, not a JWT (JWTs start with eyJ)
        assert not token.startswith("eyJ")
        assert len(token) == 32  # 16 bytes hex

    def test_tokens_consistent_across_requests(self, sandbox_client):
        """Static sandbox token should be same across requests."""
        r1 = sandbox_client.get("/api/capabilities")
        r2 = sandbox_client.get("/api/capabilities")
        t1 = r1.json()["services"]["sandbox"]["token"]
        t2 = r2.json()["services"]["sandbox"]["token"]
        assert t1 == t2

    def test_cache_control_with_services(self, sandbox_client):
        """Response with tokens should have no-store cache control."""
        r = sandbox_client.get("/api/capabilities")
        assert r.headers.get("cache-control") == "no-store"
        assert r.headers.get("pragma") == "no-cache"

    def test_no_cache_headers_without_services(self, no_sandbox_client):
        """Response without tokens should not have restrictive cache headers."""
        r = no_sandbox_client.get("/api/capabilities")
        assert r.headers.get("cache-control") != "no-store"
