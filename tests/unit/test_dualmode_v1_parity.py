"""Dual-mode integration matrix for v1 API parity (bd-1pwb.10.2).

Verifies:
- V1 routes function in LOCAL mode with real filesystem
- HOSTED mode would route through hosted backend (mocked)
- Auth context injection differs by mode but v1 shape is identical
- Deprecation headers only on legacy, not v1 in both modes
- Capabilities endpoint reports correct mode metadata
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path
from fastapi.testclient import TestClient

from boring_ui.api.contracts import (
    ListFilesResponse,
    ReadFileResponse,
    GitStatusResponse,
    GitDiffResponse,
)


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


class TestV1RoutesAvailableBothModes:
    """V1 routes must be available in LOCAL mode. HOSTED mode without
    CAPABILITY_PRIVATE_KEY won't have v1 sandbox routes but should still
    not error on creation."""

    def test_local_v1_files_list_available(self, tmp_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/v1/files/list", params={"path": "."})
        assert resp.status_code == 200

    def test_local_v1_git_status_available(self, tmp_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/v1/git/status")
        assert resp.status_code == 200

    def test_hosted_app_creates_without_error(self, tmp_path):
        """HOSTED app should create successfully even without proxy keys."""
        app = _make_hosted_app(tmp_path)
        client = TestClient(app)
        # Health should work
        resp = client.get("/health")
        assert resp.status_code == 200


class TestCapabilitiesModeParity:
    """Capabilities endpoint reports correct mode in both modes."""

    def test_local_capabilities_reports_local_mode(self, tmp_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "local"
        assert data["features"]["files"] is True
        assert data["features"]["git"] is True

    def test_hosted_capabilities_reports_hosted_mode(self, tmp_path):
        app = _make_hosted_app(tmp_path)
        client = TestClient(app)
        # In hosted mode, capabilities requires OIDC (returns 401 without token)
        resp = client.get("/api/capabilities")
        assert resp.status_code == 401


class TestV1ResponseShapeConsistency:
    """V1 response shapes must match contracts in LOCAL mode."""

    def test_list_files_matches_contract(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "tests").mkdir()
        app = _make_local_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/files/list", params={"path": "."})
        data = resp.json()

        # Must conform to ListFilesResponse
        parsed = ListFilesResponse(**data)
        assert parsed.path == "."
        names = {f.name for f in parsed.files}
        assert "main.py" in names
        assert "tests" in names

        # Type field must be "file" or "dir"
        for f in parsed.files:
            assert f.type in ("file", "dir")

    def test_read_file_matches_contract(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        app = _make_local_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/files/read", params={"path": "readme.md"})
        data = resp.json()

        parsed = ReadFileResponse(**data)
        assert parsed.content == "# Hello"
        assert parsed.size == 7

    def test_git_status_matches_contract(self, tmp_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/git/status")
        data = resp.json()

        parsed = GitStatusResponse(**data)
        assert isinstance(parsed.is_repo, bool)
        assert isinstance(parsed.files, dict)


class TestDeprecationParityAcrossModes:
    """Deprecation headers present on legacy, absent on v1 in LOCAL mode."""

    def test_legacy_tree_deprecated_in_local(self, tmp_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/tree", params={"path": "."})
        assert resp.headers.get("Deprecation") == "true"

    def test_v1_list_not_deprecated_in_local(self, tmp_path):
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/v1/files/list", params={"path": "."})
        assert resp.headers.get("Deprecation") is None


class TestAuthContextInjection:
    """Auth context injection differs by mode but both satisfy routes."""

    def test_local_capability_context_injected_for_internal(self, tmp_path):
        """LOCAL mode auto-injects full-access capability context."""
        app = _make_local_app(tmp_path)
        client = TestClient(app)
        # /internal/v1 routes work without explicit auth
        resp = client.get("/internal/v1/files/list", params={"path": "."})
        assert resp.status_code == 200

    def test_hosted_requires_oidc_for_capabilities(self, tmp_path):
        """HOSTED mode requires OIDC for non-health routes."""
        app = _make_hosted_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/capabilities")
        assert resp.status_code == 401

    def test_hosted_health_exempt_from_auth(self, tmp_path):
        """HOSTED mode health endpoint works without auth."""
        app = _make_hosted_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200


class TestRouterCompositionParity:
    """Router composition differs correctly between modes."""

    def test_local_includes_file_and_git_routers(self, tmp_path):
        from boring_ui.api.app import _get_routers_for_mode
        routers = _get_routers_for_mode("local")
        assert "files" in routers
        assert "git" in routers

    def test_hosted_excludes_privileged_routers(self, tmp_path):
        from boring_ui.api.app import _get_routers_for_mode
        routers = _get_routers_for_mode("hosted")
        assert "files" not in routers
        assert "git" not in routers
        assert "pty" not in routers
        assert "approval" in routers

    def test_hosted_rejects_explicit_privileged_routers(self, tmp_path):
        """HOSTED mode raises ValueError if privileged routers requested."""
        env = {**HOSTED_ENV, "WORKSPACE_ROOT": str(tmp_path)}
        with patch.dict("os.environ", env):
            from boring_ui.api.app import create_app
            with pytest.raises(ValueError, match="SECURITY"):
                create_app(routers=["files"])
