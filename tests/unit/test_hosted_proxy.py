"""Tests for hosted proxy handlers (bd-1pwb.5.2 files/git, bd-1pwb.5.3 exec).

Verifies:
- Pre-forward authz checks via @require_permission
- Capability token issuance before forwarding
- Error mapping (502 on sandbox failure)
- Timeout enforcement for exec
- No direct privileged execution in hosted mode
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from boring_ui.api.modules.sandbox.hosted_proxy import create_hosted_sandbox_proxy_router
from boring_ui.api.modules.sandbox.hosted_client import (
    HostedSandboxClient,
    SandboxClientConfig,
    SandboxClientError,
)


def _make_mock_issuer():
    issuer = MagicMock()
    issuer.issue_token.return_value = "cap-tok-xyz"
    return issuer


def _make_mock_client():
    config = SandboxClientConfig(internal_url="http://127.0.0.1:2469")
    client = HostedSandboxClient(config)
    client.list_files = AsyncMock(return_value={"files": [{"name": "a.py"}]})
    client.read_file = AsyncMock(return_value={"content": "hello"})
    client.write_file = AsyncMock(return_value={"success": True})
    client.git_status = AsyncMock(return_value={"branch": "main"})
    client.git_diff = AsyncMock(return_value={"diff": "+line"})
    client.exec_run = AsyncMock(return_value={"exit_code": 0, "stdout": "ok"})
    return client


def _make_app_with_auth(client, issuer):
    """Create app with proxy router and mock auth context."""
    app = FastAPI()

    # Inject mock auth context via middleware
    @app.middleware("http")
    async def inject_auth(request, call_next):
        from boring_ui.api.auth_middleware import AuthContext
        request.state.auth_context = AuthContext(
            user_id="test-user",
            workspace_id="ws-123",
            permissions={"files:read", "files:write", "git:read", "exec:run"},
            claims={},
        )
        return await call_next(request)

    router = create_hosted_sandbox_proxy_router(client, issuer)
    app.include_router(router, prefix="/api/v1")
    return app


class TestHostedFilesProxy:
    """bd-1pwb.5.2: Hosted files proxy handlers."""

    def test_list_files_proxies_to_client(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/files/list", params={"path": "src/"})
        assert resp.status_code == 200
        client.list_files.assert_called_once()
        assert "request_id" in client.list_files.call_args[1]
        # Verify capability token was issued
        issuer.issue_token.assert_called()

    def test_read_file_proxies_to_client(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/files/read", params={"path": "main.py"})
        assert resp.status_code == 200
        client.read_file.assert_called_once()

    def test_write_file_proxies_to_client(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.post(
            "/api/v1/sandbox/proxy/files/write",
            params={"path": "out.txt", "content": "data"},
        )
        assert resp.status_code == 200
        client.write_file.assert_called_once()

    def test_list_files_error_returns_502(self):
        client = _make_mock_client()
        client.list_files = AsyncMock(side_effect=Exception("sandbox down"))
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/files/list", params={"path": "."})
        assert resp.status_code == 502

    def test_capability_token_scoped_to_operation(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        tc.get("/api/v1/sandbox/proxy/files/list", params={"path": "."})
        call_kwargs = issuer.issue_token.call_args[1]
        assert call_kwargs["operations"] == {"files:list"}
        assert call_kwargs["ttl_seconds"] == 60


class TestHostedGitProxy:
    """bd-1pwb.5.2: Hosted git proxy handlers."""

    def test_git_status_proxies(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/git/status")
        assert resp.status_code == 200
        client.git_status.assert_called_once()
        assert "request_id" in client.git_status.call_args[1]

    def test_git_diff_proxies(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/git/diff", params={"context": "staged"})
        assert resp.status_code == 200
        client.git_diff.assert_called_once()
        assert "request_id" in client.git_diff.call_args[1]

    def test_git_status_error_returns_502(self):
        client = _make_mock_client()
        client.git_status = AsyncMock(side_effect=Exception("sandbox unreachable"))
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/git/status")
        assert resp.status_code == 502

    def test_files_typed_timeout_error_maps_to_504(self):
        client = _make_mock_client()
        client.list_files = AsyncMock(
            side_effect=SandboxClientError(
                code="sandbox_timeout",
                message="sandbox request timed out",
                http_status=504,
                request_id="req-files-1",
                trace_id="trace-files-1",
            )
        )
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/files/list", params={"path": "."})
        assert resp.status_code == 504
        data = resp.json()["detail"]
        assert data["error"] == "sandbox_timeout"
        assert data["request_id"] == "req-files-1"


class TestHostedExecProxy:
    """bd-1pwb.5.3: Hosted exec proxy handlers."""

    def test_exec_run_proxies(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.post(
            "/api/v1/sandbox/proxy/exec/run",
            params={"command": "ls -la", "timeout_seconds": 30},
        )
        assert resp.status_code == 200
        client.exec_run.assert_called_once()
        call_kwargs = client.exec_run.call_args[1]
        assert "request_id" in call_kwargs

    def test_exec_timeout_capped_at_300(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        tc.post(
            "/api/v1/sandbox/proxy/exec/run",
            params={"command": "long-cmd", "timeout_seconds": 999},
        )
        # Timeout should be capped to 300
        call_args = client.exec_run.call_args
        assert call_args[0][1] == 300  # second positional arg is timeout

    def test_exec_negative_timeout_defaults_to_30(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        tc.post(
            "/api/v1/sandbox/proxy/exec/run",
            params={"command": "cmd", "timeout_seconds": -5},
        )
        call_args = client.exec_run.call_args
        assert call_args[0][1] == 30

    def test_exec_sandbox_timeout_maps_to_504(self):
        client = _make_mock_client()
        client.exec_run = AsyncMock(
            side_effect=SandboxClientError(
                code="sandbox_timeout",
                message="sandbox request timed out",
                http_status=504,
                request_id="req-123",
                trace_id="trace-abc",
            )
        )
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.post(
            "/api/v1/sandbox/proxy/exec/run",
            params={"command": "bad-cmd"},
        )
        assert resp.status_code == 504
        data = resp.json()["detail"]
        assert data["error"] == "sandbox_timeout"
        assert data["request_id"] == "req-123"
        assert data["trace_id"] == "trace-abc"

    def test_exec_untyped_error_maps_to_502(self):
        client = _make_mock_client()
        client.exec_run = AsyncMock(side_effect=RuntimeError("boom"))
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.post(
            "/api/v1/sandbox/proxy/exec/run",
            params={"command": "bad-cmd"},
        )
        assert resp.status_code == 502
        data = resp.json()["detail"]
        assert data["error"] == "proxy_exec_failed"

    def test_exec_capability_scoped(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        tc.post(
            "/api/v1/sandbox/proxy/exec/run",
            params={"command": "echo hi"},
        )
        call_kwargs = issuer.issue_token.call_args[1]
        assert call_kwargs["operations"] == {"exec:run"}


class TestProxyHealth:
    """Proxy health endpoint."""

    def test_health_returns_stats(self):
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = _make_app_with_auth(client, issuer)
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "sandbox-proxy"


class TestAuthzEnforcement:
    """Authorization enforced before forwarding."""

    def test_no_auth_context_returns_401(self):
        """Without auth middleware, proxy returns 401."""
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = FastAPI()
        router = create_hosted_sandbox_proxy_router(client, issuer)
        app.include_router(router, prefix="/api/v1")
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/files/list", params={"path": "."})
        # Should fail because no auth context injected
        assert resp.status_code in (401, 403, 500)

    def test_insufficient_permissions_blocked(self):
        """Auth context without matching permission is rejected."""
        client = _make_mock_client()
        issuer = _make_mock_issuer()
        app = FastAPI()

        @app.middleware("http")
        async def inject_limited_auth(request, call_next):
            from boring_ui.api.auth_middleware import AuthContext
            request.state.auth_context = AuthContext(
                user_id="test-user",
                workspace_id="ws-123",
                permissions={"chat:read"},  # No files:read
                claims={},
            )
            return await call_next(request)

        router = create_hosted_sandbox_proxy_router(client, issuer)
        app.include_router(router, prefix="/api/v1")
        tc = TestClient(app)

        resp = tc.get("/api/v1/sandbox/proxy/files/list", params={"path": "."})
        assert resp.status_code == 403
