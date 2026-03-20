"""E2E integration test for backend-agent mode.

Starts the full app with AGENTS_MODE=backend, verifies:
- Health endpoint works with PI harness status
- Capabilities report backend mode + PI agent
- Exec endpoint runs commands on workspace
- File operations work (write + read + list)
- PI agent routes are mounted
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from boring_ui.api.app import create_app
from boring_ui.api.config import APIConfig, AgentRuntimeConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(tmp_path):
    """Create a temporary workspace with sample files for backend-agent mode."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "README.md").write_text("# Backend Agent Test")
    (ws / "src").mkdir()
    (ws / "src" / "hello.py").write_text('print("hello")')
    return ws


@pytest.fixture
def backend_app(workspace, monkeypatch):
    """Create a full application in backend-agent mode.

    Control plane is disabled (no DATABASE_URL) to match the workspace-VM
    role where agents_mode=backend and no DB is present.
    """
    monkeypatch.setenv("AGENTS_MODE", "backend")
    monkeypatch.setenv("BORING_UI_WORKSPACE_ROOT", str(workspace))
    monkeypatch.setenv("BORING_UI_SESSION_SECRET", "test-secret-for-e2e")
    # Disable control plane for workspace-VM role
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CONTROL_PLANE_ENABLED", raising=False)

    config = APIConfig(
        workspace_root=workspace,
        agents_mode="backend",
        agents={"pi": AgentRuntimeConfig(enabled=True, port=19999)},
        control_plane_enabled=False,
    )
    app = create_app(config, include_pty=False, include_stream=False)
    return app


@pytest.fixture
def frontend_app(workspace, monkeypatch):
    """Create a full application in frontend (default) mode."""
    monkeypatch.setenv("BORING_UI_WORKSPACE_ROOT", str(workspace))
    monkeypatch.setenv("BORING_UI_SESSION_SECRET", "test-secret-for-e2e")
    monkeypatch.delenv("AGENTS_MODE", raising=False)

    config = APIConfig(
        workspace_root=workspace,
        agents_mode="frontend",
        control_plane_enabled=False,
    )
    app = create_app(config, include_pty=False, include_stream=False)
    return app


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestBackendModeHealth:
    """Health endpoints in backend-agent mode."""

    @pytest.mark.asyncio
    async def test_backend_mode_health_reports_pi_status(self, backend_app, workspace):
        """GET /healthz should include a 'pi' check in its response."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/healthz")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "pi" in data["checks"]
            # PI harness is registered but sidecar is not running, so
            # the check should report degraded (not a crash).
            assert data["checks"]["pi"] in ("ok", "degraded")

    @pytest.mark.asyncio
    async def test_backend_mode_health_includes_workspace(self, backend_app, workspace):
        """GET /health should report the workspace root."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["workspace"] == str(workspace)


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

class TestBackendModeCapabilities:
    """Capabilities endpoint in backend-agent mode."""

    @pytest.mark.asyncio
    async def test_backend_mode_capabilities(self, backend_app):
        """GET /api/capabilities should report backend mode + pi agent."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/capabilities")
            assert response.status_code == 200
            data = response.json()

            # Agent mode
            assert data["agent_mode"] == "backend"

            # PI agent listed
            assert "pi" in data["agents"]

            # Control plane is disabled in workspace-VM role
            features = data["features"]
            assert features["control_plane"] is False

            # PI feature: True at config level, but may be False at runtime
            # if the sidecar is not actually running. The capabilities
            # endpoint queries pi_harness.healthy() which overrides the
            # static flag. In this test env the sidecar is not started,
            # so we just verify the key exists.
            assert "pi" in features

    @pytest.mark.asyncio
    async def test_backend_mode_workspace_runtime(self, backend_app):
        """Capabilities should include workspace_runtime block."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/capabilities")
            data = response.json()
            assert "workspace_runtime" in data
            assert data["workspace_runtime"]["agent_mode"] == "backend"


# ---------------------------------------------------------------------------
# Exec endpoint
# ---------------------------------------------------------------------------

class TestBackendModeExec:
    """Exec endpoint available only in backend-agent mode."""

    @pytest.mark.asyncio
    async def test_backend_mode_exec_endpoint(self, backend_app, workspace):
        """POST /api/v1/sandbox/exec should run a command and return stdout."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sandbox/exec",
                json={"command": "echo hello-backend"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["exit_code"] == 0
            assert "hello-backend" in data["stdout"]
            assert data["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_backend_mode_exec_timeout(self, backend_app):
        """A command exceeding timeout should be killed and return exit_code 124."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sandbox/exec",
                json={"command": "sleep 60", "timeout_seconds": 1},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["exit_code"] == 124
            assert "timed out" in data["stderr"].lower()

    @pytest.mark.asyncio
    async def test_backend_mode_exec_cwd_traversal_rejected(self, backend_app):
        """cwd=../../etc should return 400 (path traversal)."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sandbox/exec",
                json={"command": "pwd", "cwd": "../../etc"},
            )
            assert response.status_code == 400
            assert "workspace root" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_backend_mode_exec_absolute_traversal_rejected(self, backend_app):
        """cwd=/etc should return 400 (absolute path traversal)."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sandbox/exec",
                json={"command": "pwd", "cwd": "/etc"},
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_backend_mode_exec_cwd_within_workspace(self, backend_app, workspace):
        """cwd pointing to a subdirectory within workspace should work."""
        subdir = workspace / "subdir"
        subdir.mkdir()
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sandbox/exec",
                json={"command": "pwd", "cwd": "subdir"},
            )
            assert response.status_code == 200
            assert "subdir" in response.json()["stdout"]


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

class TestBackendModeFileOps:
    """File write/read/list via the standard file routes."""

    @pytest.mark.asyncio
    async def test_backend_mode_file_write_and_read(self, backend_app, workspace):
        """PUT write + GET read roundtrip should produce identical content."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Write
            write_resp = await client.put(
                "/api/v1/files/write?path=test-file.txt",
                json={"content": "backend-agent-content"},
            )
            assert write_resp.status_code == 200

            # Verify on disk
            assert (workspace / "test-file.txt").read_text() == "backend-agent-content"

            # Read back via API
            read_resp = await client.get("/api/v1/files/read?path=test-file.txt")
            assert read_resp.status_code == 200
            assert read_resp.json()["content"] == "backend-agent-content"

    @pytest.mark.asyncio
    async def test_backend_mode_file_list(self, backend_app, workspace):
        """GET list should show files in the workspace."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Create a new file first
            await client.put(
                "/api/v1/files/write?path=listed-file.txt",
                json={"content": "hello"},
            )

            # List root
            list_resp = await client.get("/api/v1/files/list?path=.")
            assert list_resp.status_code == 200
            data = list_resp.json()
            names = [e["name"] for e in data["entries"]]
            assert "listed-file.txt" in names
            assert "README.md" in names

    @pytest.mark.asyncio
    async def test_backend_mode_file_write_creates_nested_dirs(self, backend_app, workspace):
        """Writing to a nested path should create intermediate directories."""
        transport = ASGITransport(app=backend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            write_resp = await client.put(
                "/api/v1/files/write?path=deep/nested/file.txt",
                json={"content": "nested-content"},
            )
            assert write_resp.status_code == 200
            assert (workspace / "deep" / "nested" / "file.txt").read_text() == "nested-content"


# ---------------------------------------------------------------------------
# PI routes mounted
# ---------------------------------------------------------------------------

class TestBackendModePiRoutes:
    """PI agent routes should be mounted in backend-agent mode."""

    def test_backend_mode_pi_routes_mounted(self, backend_app):
        """PI session routes should exist in the app's route table."""
        paths = [r.path for r in backend_app.routes if hasattr(r, "path")]
        # PI harness proxy routes
        assert "/api/v1/agent/pi/sessions" in paths
        assert "/api/v1/agent/pi/sessions/create" in paths

    def test_backend_mode_exec_route_mounted(self, backend_app):
        """Exec route should be mounted in backend mode."""
        paths = [r.path for r in backend_app.routes if hasattr(r, "path")]
        assert "/api/v1/sandbox/exec" in paths


# ---------------------------------------------------------------------------
# Frontend mode contrast
# ---------------------------------------------------------------------------

class TestFrontendModeContrast:
    """Verify exec endpoint is NOT mounted in frontend mode."""

    def test_frontend_mode_no_exec_endpoint(self, frontend_app):
        """In frontend mode, the exec endpoint should not exist."""
        paths = [r.path for r in frontend_app.routes if hasattr(r, "path")]
        assert "/api/v1/sandbox/exec" not in paths

    @pytest.mark.asyncio
    async def test_frontend_mode_exec_returns_404(self, frontend_app):
        """POST to exec in frontend mode should return 404/405."""
        transport = ASGITransport(app=frontend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sandbox/exec",
                json={"command": "echo hello"},
            )
            # 404 (route not found) or 405 (method not allowed)
            assert response.status_code in (404, 405)

    @pytest.mark.asyncio
    async def test_frontend_mode_capabilities_show_frontend(self, frontend_app):
        """Capabilities in frontend mode should report agent_mode=frontend."""
        transport = ASGITransport(app=frontend_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/capabilities")
            data = response.json()
            assert data["agent_mode"] == "frontend"
            # No workspace_runtime block in frontend mode
            assert "workspace_runtime" not in data
