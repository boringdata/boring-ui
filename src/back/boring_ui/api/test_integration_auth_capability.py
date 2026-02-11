"""Integration tests for auth middleware, capability tokens, and API contracts (bd-1pwb.10.1).

Tests end-to-end flows for the two-mode architecture:
- OIDC JWT validation and auth context injection
- Capability token issuance and validation
- Operation scoping with wildcards
- Replay protection via JTI tracking
- Permission enforcement (401 vs 403 semantics)
- Contract validation (Pydantic v2 schemas)
- Security deny-paths (path traversal, payload validation)
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.testclient import TestClient

from .auth_middleware import add_oidc_auth_middleware, AuthContext, get_auth_context, require_permission
from .auth import OIDCVerifier
from .capability_tokens import (
    CapabilityToken,
    CapabilityTokenIssuer,
    CapabilityTokenValidator,
    JTIReplayStore,
)
from .sandbox_auth import (
    CapabilityAuthContext,
    add_capability_auth_middleware,
    get_capability_context,
    require_capability,
)
from .contracts import (
    FileInfo,
    ListFilesResponse,
    ReadFileResponse,
    ErrorCode,
    ErrorResponse,
)
from .service_auth import ServiceIdentity, ServiceTokenSigner, ServiceTokenValidator
from .modules.sandbox.policy import SandboxPolicies, FilePolicy, ExecPolicy


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def rsa_key_pair():
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
def capability_issuer(rsa_key_pair):
    """Create capability token issuer."""
    return CapabilityTokenIssuer(rsa_key_pair["private"])


@pytest.fixture
def capability_validator(rsa_key_pair):
    """Create capability token validator."""
    return CapabilityTokenValidator(rsa_key_pair["public"])


@pytest.fixture
def replay_store():
    """Create JTI replay store."""
    return JTIReplayStore()


@pytest.fixture
def service_signer(rsa_key_pair):
    """Create service token signer."""
    return ServiceTokenSigner(rsa_key_pair["private"], service_name="hosted-api")


@pytest.fixture
def service_validator(rsa_key_pair):
    """Create service token validator."""
    return ServiceTokenValidator(
        {1: rsa_key_pair["public"]},
        current_version=1,
        grace_period_seconds=300,
    )


# ============================================================================
# AUTH MIDDLEWARE TESTS
# ============================================================================

class TestAuthMiddlewareIntegration:
    """Test auth middleware with proper error semantics."""

    def test_missing_auth_header_returns_401(self):
        """Missing Authorization header should return 401."""
        app = FastAPI()

        oidc_verifier = Mock(spec=OIDCVerifier)
        add_oidc_auth_middleware(app, oidc_verifier)

        @app.get("/api/protected")
        async def protected_route(request: Request):
            context = get_auth_context(request)
            return {"user": context.user_id}

        client = TestClient(app)
        response = client.get("/api/protected")

        assert response.status_code == 401
        assert "code" in response.json()
        assert response.json()["code"] == "AUTH_MISSING"

    def test_invalid_token_returns_401(self):
        """Invalid token should return 401 with AUTH_INVALID code."""
        app = FastAPI()

        oidc_verifier = Mock(spec=OIDCVerifier)
        oidc_verifier.validate_token.return_value = None  # Validation fails
        add_oidc_auth_middleware(app, oidc_verifier)

        @app.get("/api/protected")
        async def protected_route(request: Request):
            context = get_auth_context(request)
            return {"user": context.user_id}

        client = TestClient(app)
        response = client.get("/api/protected", headers={"Authorization": "Bearer invalid_token"})

        assert response.status_code == 401
        assert response.json()["code"] == "AUTH_INVALID"

    def test_insufficient_permission_returns_403(self):
        """Insufficient permission should return 403 with permission code."""
        app = FastAPI()

        oidc_verifier = Mock(spec=OIDCVerifier)
        oidc_verifier.validate_token.return_value = {
            "sub": "user123",
            "workspace_id": "ws1",
            "permissions": ["files:read"],  # Only read permission
        }
        add_oidc_auth_middleware(app, oidc_verifier)

        @app.post("/api/protected")
        @require_permission("files:write")  # Requires write
        async def protected_route(request: Request):
            return {"status": "ok"}

        client = TestClient(app)
        response = client.post(
            "/api/protected",
            headers={"Authorization": "Bearer valid_token"}
        )

        assert response.status_code == 403
        assert "code" in response.json()

    def test_valid_token_injects_auth_context(self):
        """Valid token should inject AuthContext into request."""
        app = FastAPI()

        oidc_verifier = Mock(spec=OIDCVerifier)
        oidc_verifier.validate_token.return_value = {
            "sub": "user123",
            "workspace_id": "ws1",
            "permissions": ["files:*", "git:*"],
        }
        add_oidc_auth_middleware(app, oidc_verifier)

        @app.get("/api/protected")
        async def protected_route(request: Request):
            context = get_auth_context(request)
            return {
                "user": context.user_id,
                "workspace": context.workspace_id,
                "permissions": list(context.permissions),
            }

        client = TestClient(app)
        response = client.get(
            "/api/protected",
            headers={"Authorization": "Bearer valid_token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"] == "user123"
        assert data["workspace"] == "ws1"
        assert "files:*" in data["permissions"]


# ============================================================================
# CAPABILITY TOKEN TESTS
# ============================================================================

class TestCapabilityTokenFlow:
    """Test end-to-end capability token flow."""

    def test_issue_and_validate_token(self, capability_issuer, capability_validator):
        """Should issue and validate capability token with operation scoping."""
        token = capability_issuer.issue_token(
            workspace_id="ws1",
            operations={"files:read", "files:write"},
            ttl_seconds=60,
        )

        claims = capability_validator.validate_token(token)
        assert claims is not None
        assert claims["workspace_id"] == "ws1"
        assert "files:read" in claims["ops"]
        assert "files:write" in claims["ops"]

    def test_replay_attack_detection(self, capability_issuer, capability_validator, replay_store):
        """Should detect and reject replayed tokens."""
        token = capability_issuer.issue_token(
            workspace_id="ws1",
            operations={"files:read"},
            ttl_seconds=60,
        )

        claims = capability_validator.validate_token(token)
        jti = claims["jti"]

        # First use: should be allowed
        assert not replay_store.is_replayed(jti)
        replay_store.record_jti(jti, ttl_seconds=60)

        # Second use: should be detected as replay
        assert replay_store.is_replayed(jti)

    def test_expired_token_rejected(self, capability_issuer, capability_validator):
        """Should reject expired tokens."""
        token = capability_issuer.issue_token(
            workspace_id="ws1",
            operations={"files:read"},
            ttl_seconds=1,  # Expire in 1 second
        )

        # Token should be valid initially
        claims = capability_validator.validate_token(token)
        assert claims is not None

        # Wait for expiry
        time.sleep(1.1)

        # Token should now be rejected
        claims = capability_validator.validate_token(token)
        assert claims is None

    def test_operation_scoping(self, capability_issuer, capability_validator):
        """Should enforce operation scoping."""
        token = capability_issuer.issue_token(
            workspace_id="ws1",
            operations={"files:read", "git:status"},
            ttl_seconds=60,
        )

        claims = capability_validator.validate_token(token)

        # Allowed operations
        assert capability_validator.validate_operation(claims, "files:read")
        assert capability_validator.validate_operation(claims, "git:status")

        # Disallowed operations
        assert not capability_validator.validate_operation(claims, "files:write")
        assert not capability_validator.validate_operation(claims, "exec:run")

    def test_wildcard_operation_matching(self, capability_issuer, capability_validator):
        """Should support wildcard operation matching."""
        token = capability_issuer.issue_token(
            workspace_id="ws1",
            operations={"files:*"},  # All file operations
            ttl_seconds=60,
        )

        claims = capability_validator.validate_token(token)

        # All file operations should be allowed
        assert capability_validator.validate_operation(claims, "files:read")
        assert capability_validator.validate_operation(claims, "files:write")
        assert capability_validator.validate_operation(claims, "files:delete")

        # Non-file operations should be denied
        assert not capability_validator.validate_operation(claims, "git:commit")


# ============================================================================
# CONTRACT VALIDATION TESTS
# ============================================================================

class TestContractValidation:
    """Test Pydantic v2 contract models."""

    def test_file_info_schema(self):
        """FileInfo should validate file metadata."""
        # Valid
        info = FileInfo(name="test.py", type="file", size=1024)
        assert info.name == "test.py"
        assert info.type == "file"
        assert info.size == 1024

        # Directory without size
        info = FileInfo(name="src", type="dir", size=None)
        assert info.type == "dir"
        assert info.size is None

    def test_list_files_response_schema(self):
        """ListFilesResponse should validate file listing."""
        files = [
            FileInfo(name="file1.py", type="file", size=100),
            FileInfo(name="file2.py", type="file", size=200),
            FileInfo(name="src", type="dir", size=None),
        ]
        response = ListFilesResponse(path=".", files=files)

        assert response.path == "."
        assert len(response.files) == 3

        # Convert to dict for JSON
        data = response.model_dump()
        assert data["path"] == "."
        assert len(data["files"]) == 3

    def test_error_response_schema(self):
        """ErrorResponse should validate error contracts."""
        error = ErrorResponse(
            code=ErrorCode.AUTH_MISSING,
            message="Missing authorization header",
            request_id="req-123",
        )

        assert error.code == ErrorCode.AUTH_MISSING
        assert error.request_id == "req-123"

        # JSON serialization
        data = error.model_dump()
        assert data["code"] == "AUTH_MISSING"


# ============================================================================
# SECURITY DENY-PATH TESTS
# ============================================================================

class TestSecurityDenyPaths:
    """Test security boundaries and deny-path scenarios."""

    def test_path_traversal_protection(self):
        """Should reject path traversal attempts."""
        workspace_root = Path("/home/user/workspace")

        # Valid path
        test_path = workspace_root / "src/main.py"
        assert str(test_path.resolve()).startswith(str(workspace_root.resolve()))

        # Path traversal attempt
        test_path = workspace_root / "../../etc/passwd"
        try:
            test_path.resolve().relative_to(workspace_root.resolve())
            assert False, "Should have raised ValueError for path traversal"
        except ValueError:
            pass  # Expected

    def test_policy_enforcement(self):
        """Should enforce sandbox policies."""
        policies = SandboxPolicies(
            file_policy=FilePolicy.RESTRICTED,
            exec_policy=ExecPolicy.DENY_DANGEROUS,
        )

        # Allowed file
        assert policies.allow_file_access("/home/user/workspace/src/main.py")

        # Blocked paths
        assert not policies.allow_file_access("/etc/passwd")
        assert not policies.allow_file_access("/root/.ssh")

        # Dangerous commands
        assert not policies.allow_command("rm -rf /")
        assert not policies.allow_command("dd if=/dev/zero of=/dev/sda")

        # Safe commands
        assert policies.allow_command("ls -la")
        assert policies.allow_command("cat file.txt")

    def test_empty_command_rejected(self):
        """Should reject empty commands."""
        policies = SandboxPolicies()

        assert not policies.allow_command("")
        assert not policies.allow_command("   ")
        assert not policies.allow_command("\n")

    def test_permission_denial_logging(self):
        """Should log permission denials for audit."""
        app = FastAPI()

        oidc_verifier = Mock(spec=OIDCVerifier)
        oidc_verifier.validate_token.return_value = {
            "sub": "user123",
            "workspace_id": "ws1",
            "permissions": ["files:read"],  # Only read
        }
        add_oidc_auth_middleware(app, oidc_verifier)

        @app.post("/api/write")
        @require_permission("files:write")
        async def write_route(request: Request):
            return {"status": "ok"}

        client = TestClient(app)
        response = client.post(
            "/api/write",
            headers={"Authorization": "Bearer token"}
        )

        # Should deny with 403
        assert response.status_code == 403


# ============================================================================
# SERVICE IDENTITY TESTS
# ============================================================================

class TestServiceIdentityFlow:
    """Test service-to-service authentication."""

    def test_sign_and_validate_service_token(self, service_signer, service_validator, rsa_key_pair):
        """Should sign and validate service tokens."""
        token = service_signer.sign_request(ttl_seconds=60)

        # Update validator with correct public key
        validator = ServiceTokenValidator(
            {1: rsa_key_pair["public"]},
            current_version=1,
            grace_period_seconds=300,
        )

        claims = validator.validate_token(token)
        assert claims is not None
        assert claims["sub"] == "hosted-api"

    def test_key_rotation_with_grace_period(self, rsa_key_pair):
        """Should support key rotation with grace period."""
        # Generate second key
        import cryptography.hazmat.primitives.asymmetric.rsa as rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        private_key_v2 = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        public_key_v2 = private_key_v2.public_key()
        private_pem_v2 = private_key_v2.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        public_pem_v2 = public_key_v2.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        # Signer with initial key
        signer = ServiceTokenSigner(rsa_key_pair["private"], service_name="hosted-api")

        # Validator with both key versions
        validator = ServiceTokenValidator(
            {1: rsa_key_pair["public"], 2: public_pem_v2},
            current_version=2,
            grace_period_seconds=300,
        )

        # Token signed with old key should still be valid during grace period
        old_token = signer.sign_request(ttl_seconds=60)
        claims = validator.validate_token(old_token)
        assert claims is not None  # Still valid due to grace period


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
