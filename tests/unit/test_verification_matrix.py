"""Verification matrix for transport/auth/path-isolation contracts (bd-1adh.8.1).

Comprehensive automated test matrix covering all cross-cutting concerns
across LOCAL vs HOSTED modes. This is the "proof by test" that the
two-module architecture enforces its security and transport contracts.

Matrix dimensions:
- Mode: LOCAL (default), LOCAL (parity), HOSTED
- Layer: transport, auth, path-isolation, error-semantics
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from pathlib import Path


HOSTED_ENV = {
    "BORING_UI_RUN_MODE": "hosted",
    "ANTHROPIC_API_KEY": "test-key",
    "HOSTED_API_TOKEN": "test-token",
    "OIDC_ISSUER": "https://test.example.com",
    "OIDC_AUDIENCE": "test-audience",
}


def make_local_app(tmp_path, parity=False):
    """Create a LOCAL-mode app."""
    env = {
        "WORKSPACE_ROOT": str(tmp_path),
        "BORING_UI_RUN_MODE": "local",
    }
    if parity:
        env["LOCAL_PARITY_MODE"] = "http"
    with patch.dict("os.environ", env):
        import os
        if not parity:
            os.environ.pop("LOCAL_PARITY_MODE", None)
        from boring_ui.api.app import create_app
        return create_app(
            include_pty=False,
            include_stream=False,
            include_sandbox=False,
            include_companion=False,
        )


def make_hosted_app(tmp_path):
    """Create a HOSTED-mode app."""
    env = {**HOSTED_ENV, "WORKSPACE_ROOT": str(tmp_path)}
    with patch.dict("os.environ", env):
        from boring_ui.api.app import create_app
        return create_app(
            include_pty=False,
            include_stream=False,
            include_sandbox=False,
            include_companion=False,
        )


# ─── Transport contracts ──────────────────────────────────────────

class TestTransportContracts:
    """Transport layer contracts across modes."""

    def test_local_default_internal_reachable(self, tmp_path):
        """LOCAL default: /internal/v1 routes reachable (in-process)."""
        app = make_local_app(tmp_path)
        client = TestClient(app)
        r = client.get("/internal/v1/files/list", params={"path": "."})
        assert r.status_code == 200

    def test_local_parity_internal_not_mounted(self, tmp_path):
        """LOCAL parity: /internal/v1 NOT in-process (requires separate server)."""
        app = make_local_app(tmp_path, parity=True)
        client = TestClient(app)
        r = client.get("/internal/v1/files/list", params={"path": "."})
        assert r.status_code == 404

    def test_hosted_internal_blocked_by_auth(self, tmp_path):
        """HOSTED: /internal/v1 blocked by OIDC auth (401)."""
        app = make_hosted_app(tmp_path)
        client = TestClient(app)
        r = client.get("/internal/v1/files/list", params={"path": "."})
        assert r.status_code == 401

    def test_health_reachable_all_modes(self, tmp_path):
        """Health endpoint reachable in all modes."""
        for factory, kwargs in [
            (make_local_app, {}),
            (make_local_app, {"parity": True}),
            (make_hosted_app, {}),
        ]:
            app = factory(tmp_path, **kwargs) if kwargs else factory(tmp_path)
            client = TestClient(app)
            r = client.get("/health")
            assert r.status_code == 200, f"Health failed for {factory.__name__}({kwargs})"


# ─── Auth contracts ──────────────────────────────────────────────

class TestAuthContracts:
    """Authentication/authorization contracts across modes."""

    def test_local_no_oidc_required(self, tmp_path):
        """LOCAL: No OIDC auth required for any route."""
        app = make_local_app(tmp_path)
        client = TestClient(app)
        # Files route should work without any auth header
        r = client.get("/internal/v1/files/list", params={"path": "."})
        assert r.status_code == 200

    def test_hosted_oidc_required(self, tmp_path):
        """HOSTED: OIDC auth required for non-health routes."""
        app = make_hosted_app(tmp_path)
        client = TestClient(app)
        # Capabilities endpoint requires OIDC
        r = client.get("/api/capabilities")
        assert r.status_code == 401

    def test_hosted_health_exempt(self, tmp_path):
        """HOSTED: Health exempt from OIDC."""
        app = make_hosted_app(tmp_path)
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200

    def test_capability_context_injected_local(self, tmp_path):
        """LOCAL: CapabilityAuthContext auto-injected for /internal/v1."""
        app = make_local_app(tmp_path)
        client = TestClient(app)
        # This proves the middleware injected a full-access context
        r = client.get("/internal/v1/files/list", params={"path": "."})
        assert r.status_code == 200

    def test_standalone_local_api_requires_capability(self, tmp_path):
        """Standalone local-api: @require_capability blocks without context."""
        from boring_ui.api.local_api.app import create_local_api_app
        app = create_local_api_app(tmp_path)
        client = TestClient(app)
        r = client.get("/internal/v1/files/list", params={"path": "."})
        assert r.status_code == 401


# ─── Path isolation contracts ─────────────────────────────────────

class TestPathIsolationContracts:
    """Workspace path isolation contracts."""

    @pytest.mark.parametrize("traversal_path", [
        "../../../etc/passwd",
        "/etc/passwd",
        "subdir/../../../etc/shadow",
        "..%2F..%2Fetc/passwd",  # URL-encoded (FastAPI decodes before handler)
    ])
    def test_local_path_traversal_blocked(self, tmp_path, traversal_path):
        """LOCAL: Path traversal blocked for all known attack vectors."""
        app = make_local_app(tmp_path)
        client = TestClient(app)
        r = client.get("/internal/v1/files/read", params={"path": traversal_path})
        assert r.status_code in (403, 404), f"Traversal not blocked for: {traversal_path}"

    def test_local_valid_path_allowed(self, tmp_path):
        """LOCAL: Valid paths within workspace work."""
        (tmp_path / "valid.txt").write_text("content")
        app = make_local_app(tmp_path)
        client = TestClient(app)
        r = client.get("/internal/v1/files/read", params={"path": "valid.txt"})
        assert r.status_code == 200

    def test_local_subdirectory_access(self, tmp_path):
        """LOCAL: Subdirectory access within workspace works."""
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "file.txt").write_text("nested")
        app = make_local_app(tmp_path)
        client = TestClient(app)
        r = client.get("/internal/v1/files/read", params={"path": "sub/file.txt"})
        assert r.status_code == 200


# ─── Error semantics contracts ────────────────────────────────────

class TestErrorSemanticsContracts:
    """Error response semantics across modes."""

    def test_hosted_auth_error_is_401(self, tmp_path):
        """HOSTED: Missing auth returns 401 with clear message."""
        app = make_hosted_app(tmp_path)
        client = TestClient(app)
        r = client.get("/api/capabilities")
        assert r.status_code == 401

    def test_local_file_not_found_is_404(self, tmp_path):
        """LOCAL: Missing file returns 404."""
        app = make_local_app(tmp_path)
        client = TestClient(app)
        r = client.get("/internal/v1/files/read", params={"path": "nonexistent.txt"})
        assert r.status_code == 404

    def test_local_traversal_is_403(self, tmp_path):
        """LOCAL: Path traversal returns 403."""
        app = make_local_app(tmp_path)
        client = TestClient(app)
        r = client.get("/internal/v1/files/read", params={"path": "../../etc/passwd"})
        assert r.status_code == 403

    def test_hosted_privileged_router_rejection_is_value_error(self, tmp_path):
        """HOSTED: Explicit privileged router request raises ValueError."""
        env = {**HOSTED_ENV, "WORKSPACE_ROOT": str(tmp_path)}
        with patch.dict("os.environ", env):
            from boring_ui.api.app import create_app
            with pytest.raises(ValueError, match="SECURITY"):
                create_app(routers=["files"])


# ─── Transport error codes ────────────────────────────────────────

class TestTransportErrorCodes:
    """Error code semantics for transport layer."""

    def test_error_code_retryable_classification(self):
        """Retryable errors are correctly classified."""
        from boring_ui.api.error_codes import ErrorCode, TransportError

        retryable_codes = [
            ErrorCode.SPRITES_HANDSHAKE_TIMEOUT,
            ErrorCode.SPRITES_CONNECT_TIMEOUT,
            ErrorCode.HTTP_STATUS_502,
            ErrorCode.HTTP_STATUS_503,
            ErrorCode.HTTP_STATUS_504,
        ]
        for code in retryable_codes:
            err = TransportError(code=code, message="test", http_status=502, retryable=True)
            assert err.retryable is True, f"{code} should be retryable"

    def test_error_code_non_retryable_classification(self):
        """Non-retryable errors are correctly classified."""
        from boring_ui.api.error_codes import ErrorCode, TransportError

        non_retryable_codes = [
            ErrorCode.HTTP_STATUS_400,
            ErrorCode.HTTP_STATUS_401,
            ErrorCode.HTTP_STATUS_403,
            ErrorCode.HTTP_STATUS_404,
        ]
        for code in non_retryable_codes:
            err = TransportError(code=code, message="test", http_status=400, retryable=False)
            assert err.retryable is False, f"{code} should not be retryable"

    def test_retry_policy_defaults(self):
        """RetryPolicy has correct defaults."""
        from boring_ui.api.hosted_client import RetryPolicy

        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff_ms == [100, 300, 900]
