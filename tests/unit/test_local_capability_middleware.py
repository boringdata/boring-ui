"""Tests for LOCAL mode capability auth middleware wiring (bd-1adh.6.2).

Verifies that in LOCAL mode, /internal/v1/* routes get a full-access
CapabilityAuthContext injected by middleware, so @require_capability
decorators are satisfied without token round-trips.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pathlib import Path


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


class TestLocalCapabilityMiddleware:
    """Tests for LOCAL mode capability context injection."""

    def test_internal_routes_get_capability_context(self, local_app):
        """Internal routes receive full-access capability context in LOCAL mode."""
        app, workspace = local_app
        client = TestClient(app)

        # /internal/v1/files/list should work without any token
        response = client.get("/internal/v1/files/list", params={"path": "."})

        # Should succeed (200) because LOCAL middleware injects full-access context
        assert response.status_code == 200

    def test_internal_routes_return_file_listing(self, local_app):
        """Files route returns actual workspace listing."""
        app, workspace = local_app

        # Create a test file
        (workspace / "hello.txt").write_text("world")

        client = TestClient(app)
        response = client.get("/internal/v1/files/list", params={"path": "."})

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        names = [f["name"] for f in data["files"]]
        assert "hello.txt" in names

    def test_internal_file_read(self, local_app):
        """File read route works with injected capability context."""
        app, workspace = local_app

        # Create a test file
        (workspace / "test.txt").write_text("test content")

        client = TestClient(app)
        response = client.get("/internal/v1/files/read", params={"path": "test.txt"})

        assert response.status_code == 200

    def test_non_internal_routes_unaffected(self, local_app):
        """Non-internal routes don't get capability context injection."""
        app, _ = local_app
        client = TestClient(app)

        # /health should work (public route, no capability needed)
        response = client.get("/health")
        assert response.status_code == 200

    def test_path_traversal_still_blocked(self, local_app):
        """Path traversal is still blocked even with full-access context."""
        app, _ = local_app
        client = TestClient(app)

        response = client.get(
            "/internal/v1/files/read",
            params={"path": "../../etc/passwd"},
        )

        # Should be 403 (path traversal) not 200
        assert response.status_code == 403

    def test_git_status_route_accessible(self, local_app):
        """Git status route works with injected capability context."""
        app, workspace = local_app

        # Initialize git repo in workspace with initial commit
        import subprocess
        subprocess.run(["git", "init"], cwd=str(workspace), capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=str(workspace), capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(workspace), capture_output=True,
        )
        (workspace / ".gitkeep").write_text("")
        subprocess.run(["git", "add", "."], cwd=str(workspace), capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(workspace), capture_output=True,
        )

        client = TestClient(app)
        response = client.get("/internal/v1/git/status")

        # Should succeed — capability context allows git:status
        assert response.status_code == 200
