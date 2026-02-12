"""Security regression gates for two-mode architecture (bd-1pwb.10.3).

Adversarial security tests covering:
- Path traversal via v1 routes
- Command injection attempts through exec
- Auth bypass attempts
- Privilege escalation across modes
- OIDC bypass attempts in hosted mode
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

HOSTED_ENV = {
    "BORING_UI_RUN_MODE": "hosted",
    "ANTHROPIC_API_KEY": "test-key",
    "HOSTED_API_TOKEN": "test-token",
    "OIDC_ISSUER": "https://test.example.com",
    "OIDC_AUDIENCE": "test-audience",
}


def _make_local_app(tmp_path):
    env = {
        "WORKSPACE_ROOT": str(tmp_path),
        "BORING_UI_RUN_MODE": "local",
    }
    with patch.dict("os.environ", env):
        import os
        os.environ.pop("LOCAL_PARITY_MODE", None)
        from boring_ui.api.app import create_app
        return create_app(
            include_pty=False,
            include_stream=False,
            include_sandbox=False,
            include_companion=False,
        )


def _make_hosted_app(tmp_path):
    env = {**HOSTED_ENV, "WORKSPACE_ROOT": str(tmp_path)}
    with patch.dict("os.environ", env):
        from boring_ui.api.app import create_app
        return create_app(
            include_pty=False,
            include_stream=False,
            include_sandbox=False,
            include_companion=False,
        )


class TestV1PathTraversalGates:
    """Path traversal via v1 routes blocked in LOCAL mode."""

    @pytest.mark.parametrize("attack_path", [
        "../../../etc/passwd",
        "/etc/passwd",
        "subdir/../../../etc/shadow",
        "..%2F..%2Fetc/passwd",
        "....//....//etc/passwd",
        "%2e%2e%2f%2e%2e%2fetc/passwd",
    ])
    def test_v1_read_blocks_traversal(self, tmp_path, attack_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/v1/files/read", params={"path": attack_path})
        assert resp.status_code in (400, 403, 404), \
            f"Path traversal not blocked for v1 read: {attack_path}"

    @pytest.mark.parametrize("attack_path", [
        "../../../etc/shadow",
        "/tmp/evil",
    ])
    def test_v1_list_blocks_traversal(self, tmp_path, attack_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/v1/files/list", params={"path": attack_path})
        assert resp.status_code in (400, 403, 404), \
            f"Path traversal not blocked for v1 list: {attack_path}"

    @pytest.mark.parametrize("attack_path", [
        "../../../tmp/evil.txt",
        "/tmp/evil.txt",
    ])
    def test_v1_write_blocks_traversal(self, tmp_path, attack_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/files/write",
            json={"path": attack_path, "content": "pwned"},
        )
        assert resp.status_code in (400, 403, 404), \
            f"Path traversal not blocked for v1 write: {attack_path}"


class TestHostedAuthBypassGates:
    """Auth bypass attempts in HOSTED mode."""

    def test_hosted_v1_blocked_without_auth(self, tmp_path):
        """V1 routes in HOSTED mode require OIDC auth."""
        app = _make_hosted_app(tmp_path)
        client = TestClient(app)
        # Without CAPABILITY_PRIVATE_KEY, v1 sandbox routes won't be mounted
        # but the OIDC middleware blocks all non-health routes
        resp = client.get("/api/capabilities")
        assert resp.status_code == 401

    def test_hosted_internal_blocked(self, tmp_path):
        """/internal/v1 routes blocked in hosted mode."""
        app = _make_hosted_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/internal/v1/files/list", params={"path": "."})
        assert resp.status_code == 401

    def test_hosted_fake_bearer_rejected(self, tmp_path):
        """Fake Bearer token rejected in hosted mode."""
        app = _make_hosted_app(tmp_path)
        client = TestClient(app)
        resp = client.get(
            "/api/capabilities",
            headers={"Authorization": "Bearer fake-token-123"},
        )
        assert resp.status_code == 401

    def test_hosted_empty_bearer_rejected(self, tmp_path):
        """Empty Bearer token rejected."""
        app = _make_hosted_app(tmp_path)
        client = TestClient(app)
        resp = client.get(
            "/api/capabilities",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401


class TestPrivilegeEscalationGates:
    """Privilege escalation across modes."""

    def test_hosted_cannot_mount_privileged_routers(self, tmp_path):
        """HOSTED mode must refuse to mount privileged routers."""
        env = {**HOSTED_ENV, "WORKSPACE_ROOT": str(tmp_path)}
        with patch.dict("os.environ", env):
            from boring_ui.api.app import create_app
            for router_name in ["files", "git", "pty", "sandbox", "companion"]:
                with pytest.raises(ValueError, match="SECURITY"):
                    create_app(routers=[router_name])

    def test_standalone_local_api_requires_capability(self, tmp_path):
        """Standalone local-api requires capability context."""
        from boring_ui.api.local_api.app import create_local_api_app
        app = create_local_api_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/internal/v1/files/list", params={"path": "."})
        assert resp.status_code == 401


class TestCapabilityTokenSecurity:
    """Capability token security properties."""

    def test_token_issuance_and_validation(self):
        """Tokens issued can be validated with correct keys."""
        from boring_ui.api.capability_tokens import (
            CapabilityTokenIssuer,
            CapabilityTokenValidator,
        )
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        pub_pem = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        issuer = CapabilityTokenIssuer(priv_pem)
        validator = CapabilityTokenValidator(pub_pem)

        token = issuer.issue_token(
            workspace_id="ws-1",
            operations={"files:read"},
            ttl_seconds=60,
        )
        claims = validator.validate_token(token)
        assert claims is not None
        assert claims["workspace_id"] == "ws-1"
        assert "files:read" in claims["ops"]

    def test_token_wrong_key_rejected(self):
        """Token from wrong key pair is rejected."""
        from boring_ui.api.capability_tokens import (
            CapabilityTokenIssuer,
            CapabilityTokenValidator,
        )
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        # Key pair 1 (issuer)
        key1 = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv1 = key1.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

        # Key pair 2 (validator - different key)
        key2 = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub2 = key2.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        issuer = CapabilityTokenIssuer(priv1)
        validator = CapabilityTokenValidator(pub2)

        token = issuer.issue_token(
            workspace_id="ws-1",
            operations={"files:read"},
            ttl_seconds=60,
        )
        claims = validator.validate_token(token)
        assert claims is None  # Rejected

    def test_jti_replay_protection(self):
        """JTI replay store blocks reuse of tokens."""
        from boring_ui.api.capability_tokens import JTIReplayStore

        store = JTIReplayStore()
        assert not store.is_replayed("jti-1")
        store.record_jti("jti-1", ttl_seconds=60)
        assert store.is_replayed("jti-1")
        assert not store.is_replayed("jti-2")


class TestHealthEndpointSecurity:
    """Health endpoint available without auth in both modes."""

    def test_local_health_no_auth(self, tmp_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_hosted_health_no_auth(self, tmp_path):
        app = _make_hosted_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
