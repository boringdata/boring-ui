"""Tests for sandbox capability token validation and replay protection."""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from functools import wraps

from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient

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


class TestJTIReplayStore:
    """Tests for JTI replay detection."""

    def test_new_jti_not_replayed(self):
        """New JTI should not be flagged as replayed."""
        store = JTIReplayStore()
        jti = "unique-jti-123"
        assert store.is_replayed(jti) is False

    def test_recorded_jti_detected_as_replayed(self):
        """Previously recorded JTI should be detected as replay."""
        store = JTIReplayStore()
        jti = "recorded-jti-456"
        store.record_jti(jti, ttl_seconds=60)

        assert store.is_replayed(jti) is True

    def test_expired_jti_not_replayed(self):
        """Expired JTI should not be flagged as replayed."""
        store = JTIReplayStore()
        jti = "expired-jti-789"
        store.record_jti(jti, ttl_seconds=1)

        # Wait for expiry
        time.sleep(1.1)

        assert store.is_replayed(jti) is False

    def test_replay_store_cleans_expired_entries(self):
        """Replay store should clean up expired entries during checks."""
        store = JTIReplayStore()
        jti1 = "jti-1"
        jti2 = "jti-2"

        store.record_jti(jti1, ttl_seconds=1)
        store.record_jti(jti2, ttl_seconds=60)

        # Verify both are recorded
        assert len(store._cache) == 2

        # Wait for jti1 to expire
        time.sleep(1.1)

        # Check jti1 (should remove it during cleanup)
        assert store.is_replayed(jti1) is False

        # jti1 should be removed
        assert jti1 not in store._cache
        assert jti2 in store._cache

    def test_replay_store_evicts_oldest_on_max_size(self):
        """Replay store should evict oldest entry when exceeding max_size."""
        store = JTIReplayStore(max_size=3)

        store.record_jti("jti-1", ttl_seconds=3600)
        store.record_jti("jti-2", ttl_seconds=3600)
        store.record_jti("jti-3", ttl_seconds=3600)

        assert len(store._cache) == 3

        # Adding 4th should evict oldest (jti-1)
        store.record_jti("jti-4", ttl_seconds=3600)

        assert len(store._cache) == 3
        assert "jti-1" not in store._cache
        assert "jti-4" in store._cache

    def test_replay_store_stats(self):
        """Replay store should track hit/miss statistics."""
        store = JTIReplayStore()

        jti1 = "jti-1"
        store.record_jti(jti1, ttl_seconds=60)

        # Misses
        assert store.is_replayed("jti-2") is False
        assert store.is_replayed("jti-3") is False

        # Hits
        assert store.is_replayed(jti1) is True
        assert store.is_replayed(jti1) is True

        stats = store.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["total"] == 4
        assert stats["hit_rate"] == 0.5
        assert stats["cached_jtis"] == 1


class TestCapabilityAuthContext:
    """Tests for capability authorization context."""

    def test_context_creation(self):
        """CapabilityAuthContext should be created with proper fields."""
        context = CapabilityAuthContext(
            workspace_id="ws-123",
            operations={"files:read", "files:write"},
            jti="jti-1",
            issued_at=100,
            expires_at=200,
        )

        assert context.workspace_id == "ws-123"
        assert context.operations == {"files:read", "files:write"}
        assert context.jti == "jti-1"
        assert context.issued_at == 100
        assert context.expires_at == 200

    def test_has_operation_exact_match(self):
        """has_operation should return True for exact match."""
        context = CapabilityAuthContext(
            workspace_id="ws-123",
            operations={"files:read", "git:status"},
            jti="jti-1",
            issued_at=100,
            expires_at=200,
        )

        assert context.has_operation("files:read") is True
        assert context.has_operation("git:status") is True

    def test_has_operation_wildcard_match(self):
        """has_operation should support wildcard matching."""
        context = CapabilityAuthContext(
            workspace_id="ws-123",
            operations={"files:*", "git:read"},
            jti="jti-1",
            issued_at=100,
            expires_at=200,
        )

        assert context.has_operation("files:read") is True
        assert context.has_operation("files:write") is True
        assert context.has_operation("git:read") is True
        assert context.has_operation("git:write") is False

    def test_has_operation_full_wildcard(self):
        """has_operation should support full wildcard."""
        context = CapabilityAuthContext(
            workspace_id="ws-123",
            operations={"*"},
            jti="jti-1",
            issued_at=100,
            expires_at=200,
        )

        assert context.has_operation("files:read") is True
        assert context.has_operation("git:status") is True
        assert context.has_operation("exec:run") is True

    def test_has_operation_no_match(self):
        """has_operation should return False for denied operations."""
        context = CapabilityAuthContext(
            workspace_id="ws-123",
            operations={"files:read"},
            jti="jti-1",
            issued_at=100,
            expires_at=200,
        )

        assert context.has_operation("files:write") is False
        assert context.has_operation("git:status") is False


class TestCapabilityAuthMiddleware:
    """Tests for capability token validation middleware."""

    def setup_method(self):
        """Set up test fixtures."""
        # Generate RSA key pair for testing
        import cryptography.hazmat.primitives.asymmetric.rsa as rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        public_key = private_key.public_key()

        self.private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        self.public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def test_middleware_skips_non_protected_routes(self):
        """Middleware should skip routes outside protected prefix."""
        app = FastAPI()
        validator = CapabilityTokenValidator(self.public_key_pem)
        add_capability_auth_middleware(app, validator, required_prefix="/internal/v1")

        @app.get("/public/route")
        async def public_route(request: Request):
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/public/route")

        # Should succeed without token
        assert response.status_code == 200

    def test_middleware_requires_token_for_protected_routes(self):
        """Middleware should require token for protected routes."""
        app = FastAPI()
        validator = CapabilityTokenValidator(self.public_key_pem)
        add_capability_auth_middleware(app, validator, required_prefix="/internal/v1")

        @app.get("/internal/v1/test")
        async def protected_route(request: Request):
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/internal/v1/test")

        # Should fail without token
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == "CAP_AUTH_MISSING"

    def test_middleware_validates_token_signature(self):
        """Middleware should validate token signature."""
        app = FastAPI()
        validator = CapabilityTokenValidator(self.public_key_pem)
        add_capability_auth_middleware(app, validator, required_prefix="/internal/v1")

        @app.get("/internal/v1/test")
        async def protected_route(request: Request):
            return {"status": "ok"}

        client = TestClient(app)

        # Invalid token
        response = client.get(
            "/internal/v1/test",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["code"] == "CAP_AUTH_INVALID"

    def test_middleware_injects_capability_context(self):
        """Middleware should inject CapabilityAuthContext into request state."""
        app = FastAPI()
        issuer = CapabilityTokenIssuer(self.private_key_pem)
        validator = CapabilityTokenValidator(self.public_key_pem)
        add_capability_auth_middleware(app, validator, required_prefix="/internal/v1")

        @app.get("/internal/v1/test")
        async def protected_route(request: Request):
            context = request.state.capability_context
            return {
                "workspace": context.workspace_id,
                "ops": sorted(context.operations),
            }

        client = TestClient(app)

        # Issue a valid token
        token = issuer.issue_token("ws-123", {"files:read", "git:status"})

        response = client.get(
            "/internal/v1/test",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workspace"] == "ws-123"
        assert set(data["ops"]) == {"files:read", "git:status"}

    def test_middleware_detects_token_replay(self):
        """Middleware should detect and reject replayed tokens."""
        app = FastAPI()
        issuer = CapabilityTokenIssuer(self.private_key_pem)
        validator = CapabilityTokenValidator(self.public_key_pem)
        replay_store = JTIReplayStore()
        add_capability_auth_middleware(
            app, validator, replay_store, required_prefix="/internal/v1"
        )

        call_count = 0

        @app.get("/internal/v1/test")
        async def protected_route(request: Request):
            nonlocal call_count
            call_count += 1
            return {"status": "ok"}

        client = TestClient(app)

        # Issue token
        token = issuer.issue_token("ws-123", {"files:read"})

        # First request should succeed
        response1 = client.get(
            "/internal/v1/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response1.status_code == 200
        assert call_count == 1

        # Replay should be rejected
        response2 = client.get(
            "/internal/v1/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response2.status_code == 400
        data = response2.json()
        assert data["code"] == "CAP_REPLAY_DETECTED"

        # Handler should not be called again
        assert call_count == 1

    def test_middleware_disabled_when_validator_none(self):
        """Middleware should be disabled if validator is None."""
        app = FastAPI()
        add_capability_auth_middleware(app, None, required_prefix="/internal/v1")

        @app.get("/internal/v1/test")
        async def protected_route(request: Request):
            return {"status": "ok"}

        client = TestClient(app)

        # Should succeed without middleware (no token validation)
        response = client.get("/internal/v1/test")
        assert response.status_code == 200


class TestCapabilityDecorators:
    """Tests for @require_capability decorator."""

    def setup_method(self):
        """Set up test fixtures."""
        import cryptography.hazmat.primitives.asymmetric.rsa as rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        public_key = private_key.public_key()

        self.private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        self.public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def test_require_capability_grants_allowed_operation(self):
        """@require_capability should allow operations granted by token."""
        app = FastAPI()
        issuer = CapabilityTokenIssuer(self.private_key_pem)
        validator = CapabilityTokenValidator(self.public_key_pem)
        add_capability_auth_middleware(app, validator, required_prefix="/internal/v1")

        @app.get("/internal/v1/files/read")
        @require_capability("files:read")
        async def read_file(request: Request):
            return {"status": "ok"}

        client = TestClient(app)

        # Token with files:read permission
        token = issuer.issue_token("ws-123", {"files:read"})

        response = client.get(
            "/internal/v1/files/read",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_require_capability_denies_disallowed_operation(self):
        """@require_capability should deny operations not granted by token."""
        app = FastAPI()
        issuer = CapabilityTokenIssuer(self.private_key_pem)
        validator = CapabilityTokenValidator(self.public_key_pem)
        add_capability_auth_middleware(app, validator, required_prefix="/internal/v1")

        @app.get("/internal/v1/files/write")
        @require_capability("files:write")
        async def write_file(request: Request):
            return {"status": "ok"}

        client = TestClient(app)

        # Token with only files:read permission
        token = issuer.issue_token("ws-123", {"files:read"})

        response = client.get(
            "/internal/v1/files/write",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        data = response.json()
        assert "files:write" in data["detail"]

    def test_require_capability_respects_wildcards(self):
        """@require_capability should respect wildcard permissions."""
        app = FastAPI()
        issuer = CapabilityTokenIssuer(self.private_key_pem)
        validator = CapabilityTokenValidator(self.public_key_pem)
        add_capability_auth_middleware(app, validator, required_prefix="/internal/v1")

        @app.get("/internal/v1/files/read")
        @require_capability("files:read")
        async def read_file(request: Request):
            return {"status": "ok"}

        client = TestClient(app)

        # Token with files:* wildcard
        token = issuer.issue_token("ws-123", {"files:*"})

        response = client.get(
            "/internal/v1/files/read",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    def test_get_capability_context_requires_auth(self):
        """get_capability_context should raise 401 if not authenticated."""
        request = MagicMock()
        request.state = MagicMock()
        request.state.capability_context = None

        with pytest.raises(HTTPException) as exc_info:
            get_capability_context(request)

        assert exc_info.value.status_code == 401
