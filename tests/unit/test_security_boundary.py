"""Security boundary tests (bd-1adh.6.3).

Proves that:
1. HOSTED mode blocks unauthenticated access to /internal/v1/* (OIDC middleware)
2. HOSTED mode rejects explicit mounting of privileged routers
3. LOCAL mode /internal/v1/* routes enforce path traversal protection
4. Capability auth decorators reject unauthenticated requests when middleware absent
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pathlib import Path


HOSTED_ENV = {
    "BORING_UI_RUN_MODE": "hosted",
    "ANTHROPIC_API_KEY": "test-key",
    "HOSTED_API_TOKEN": "test-token",
    "OIDC_ISSUER": "https://test.example.com",
    "OIDC_AUDIENCE": "test-audience",
}


@pytest.fixture
def hosted_app(tmp_path):
    """Create a HOSTED-mode app (no privileged routes)."""
    env = {**HOSTED_ENV, "WORKSPACE_ROOT": str(tmp_path)}
    with patch.dict("os.environ", env):
        from boring_ui.api.app import create_app
        app = create_app(
            include_pty=False,
            include_stream=False,
            include_sandbox=False,
            include_companion=False,
        )
    return app


@pytest.fixture
def local_app(tmp_path):
    """Create a LOCAL-mode app with local_api mounted."""
    with patch.dict("os.environ", {
        "WORKSPACE_ROOT": str(tmp_path),
        "BORING_UI_RUN_MODE": "local",
    }):
        from boring_ui.api.app import create_app
        app = create_app(
            include_pty=False,
            include_stream=False,
            include_sandbox=False,
            include_companion=False,
        )
    return app, tmp_path


class TestHostedModeBlocking:
    """HOSTED mode blocks unauthenticated access to internal routes.

    In hosted mode, the OIDC auth middleware rejects any request without a
    valid JWT. This means /internal/v1/* routes are unreachable to browsers
    that don't have valid OIDC credentials — returning 401 Unauthorized.
    """

    def test_internal_files_blocked(self, hosted_app):
        """Unauthenticated request to /internal/v1/files/* returns 401."""
        client = TestClient(hosted_app)
        response = client.get("/internal/v1/files/list", params={"path": "."})
        assert response.status_code == 401

    def test_internal_git_blocked(self, hosted_app):
        """Unauthenticated request to /internal/v1/git/* returns 401."""
        client = TestClient(hosted_app)
        response = client.get("/internal/v1/git/status")
        assert response.status_code == 401

    def test_internal_exec_blocked(self, hosted_app):
        """Unauthenticated request to /internal/v1/exec/* returns 401."""
        client = TestClient(hosted_app)
        response = client.post(
            "/internal/v1/exec/run",
            json={"command": "ls"},
        )
        assert response.status_code == 401

    def test_health_still_reachable(self, hosted_app):
        """Health endpoint is exempt from OIDC auth."""
        client = TestClient(hosted_app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_hosted_route_table_excludes_legacy_compat_paths(self, hosted_app):
        """Hosted app should not mount legacy browser compatibility routes."""
        paths = {r.path for r in hosted_app.routes if hasattr(r, "path")}
        assert "/api/tree" not in paths
        assert "/api/file" not in paths
        assert "/api/search" not in paths
        assert "/api/v1/sandbox/proxy/files/list" not in paths


class TestHostedModeRejectsPrivilegedRouters:
    """HOSTED mode rejects explicit mounting of privileged routers."""

    def test_rejects_files_router(self, tmp_path):
        """Hosted mode raises ValueError when files router explicitly requested."""
        env = {**HOSTED_ENV, "WORKSPACE_ROOT": str(tmp_path)}
        with patch.dict("os.environ", env):
            from boring_ui.api.app import create_app
            with pytest.raises(ValueError, match="SECURITY"):
                create_app(routers=["files"])

    def test_rejects_git_router(self, tmp_path):
        """Hosted mode raises ValueError when git router explicitly requested."""
        env = {**HOSTED_ENV, "WORKSPACE_ROOT": str(tmp_path)}
        with patch.dict("os.environ", env):
            from boring_ui.api.app import create_app
            with pytest.raises(ValueError, match="SECURITY"):
                create_app(routers=["git"])

    def test_rejects_pty_router(self, tmp_path):
        """Hosted mode raises ValueError when pty router explicitly requested."""
        env = {**HOSTED_ENV, "WORKSPACE_ROOT": str(tmp_path)}
        with patch.dict("os.environ", env):
            from boring_ui.api.app import create_app
            with pytest.raises(ValueError, match="SECURITY"):
                create_app(routers=["pty"])


class TestLocalModePathTraversal:
    """LOCAL mode internal routes block path traversal."""

    def test_files_path_traversal_blocked(self, local_app):
        """Path traversal via ../../../etc/passwd is blocked."""
        app, _ = local_app
        client = TestClient(app)
        response = client.get(
            "/internal/v1/files/read",
            params={"path": "../../../etc/passwd"},
        )
        assert response.status_code == 403

    def test_files_absolute_path_outside_workspace_blocked(self, local_app):
        """Absolute path outside workspace is blocked."""
        app, _ = local_app
        client = TestClient(app)
        response = client.get(
            "/internal/v1/files/read",
            params={"path": "/etc/passwd"},
        )
        assert response.status_code == 403

    def test_files_dot_dot_in_middle_blocked(self, local_app):
        """Path traversal via subdir/../../../etc/passwd is blocked."""
        app, _ = local_app
        client = TestClient(app)
        response = client.get(
            "/internal/v1/files/read",
            params={"path": "subdir/../../../etc/passwd"},
        )
        assert response.status_code == 403

    def test_valid_path_within_workspace_allowed(self, local_app):
        """Path within workspace is allowed."""
        app, workspace = local_app
        (workspace / "allowed.txt").write_text("ok")
        client = TestClient(app)
        response = client.get(
            "/internal/v1/files/read",
            params={"path": "allowed.txt"},
        )
        assert response.status_code == 200


class TestCapabilityDecoratorWithoutMiddleware:
    """@require_capability rejects when middleware doesn't inject context."""

    def test_direct_route_call_without_context_returns_401(self):
        """Route with @require_capability returns 401 when no context."""
        from fastapi import FastAPI, Request
        from boring_ui.api.sandbox_auth import require_capability

        app = FastAPI()

        @app.get("/protected")
        @require_capability("files:read")
        async def protected_route(request: Request):
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/protected")
        assert response.status_code == 401
