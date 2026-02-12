"""Tests for LOCAL parity mode (bd-1adh.7.2, 7.3).

Verifies that:
1. is_local_parity_mode() reads LOCAL_PARITY_MODE env var
2. Parity mode skips in-process mounting of local_api
3. Default mode (non-parity) mounts local_api in-process
4. Parity mode stores parity URL on app state
5. Auth and URL-exposure invariants preserved in both modes
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pathlib import Path


class TestParityModeConfig:
    """Tests for is_local_parity_mode() config function."""

    def test_default_is_not_parity(self):
        """Default (no env var) is not parity mode."""
        from boring_ui.api.config import is_local_parity_mode
        with patch.dict("os.environ", {}, clear=False):
            # Remove LOCAL_PARITY_MODE if set
            import os
            os.environ.pop("LOCAL_PARITY_MODE", None)
            assert is_local_parity_mode() is False

    def test_http_enables_parity(self):
        """LOCAL_PARITY_MODE=http enables parity mode."""
        from boring_ui.api.config import is_local_parity_mode
        with patch.dict("os.environ", {"LOCAL_PARITY_MODE": "http"}):
            assert is_local_parity_mode() is True

    def test_other_values_not_parity(self):
        """Other values do not enable parity mode."""
        from boring_ui.api.config import is_local_parity_mode
        for val in ["true", "1", "yes", "on", "tcp", ""]:
            with patch.dict("os.environ", {"LOCAL_PARITY_MODE": val}):
                assert is_local_parity_mode() is False, f"Value '{val}' should not enable parity"

    def test_case_insensitive(self):
        """LOCAL_PARITY_MODE=HTTP (uppercase) enables parity mode."""
        from boring_ui.api.config import is_local_parity_mode
        with patch.dict("os.environ", {"LOCAL_PARITY_MODE": "HTTP"}):
            assert is_local_parity_mode() is True


class TestParityModeAppBehavior:
    """Tests for app.py behavior in parity mode vs default."""

    def test_default_mode_mounts_local_api(self, tmp_path):
        """Default LOCAL mode mounts local_api router in-process."""
        with patch.dict("os.environ", {
            "WORKSPACE_ROOT": str(tmp_path),
            "BORING_UI_RUN_MODE": "local",
        }):
            # Remove parity mode if set
            import os
            os.environ.pop("LOCAL_PARITY_MODE", None)

            from boring_ui.api.app import create_app
            app = create_app(
                include_pty=False,
                include_stream=False,
                include_sandbox=False,
                include_companion=False,
            )

        client = TestClient(app)
        # In default mode, /internal/v1/files/list should be accessible
        response = client.get("/internal/v1/files/list", params={"path": "."})
        assert response.status_code == 200

    def test_parity_mode_does_not_mount_local_api(self, tmp_path):
        """Parity mode does NOT mount local_api router in-process."""
        with patch.dict("os.environ", {
            "WORKSPACE_ROOT": str(tmp_path),
            "BORING_UI_RUN_MODE": "local",
            "LOCAL_PARITY_MODE": "http",
        }):
            from boring_ui.api.app import create_app
            app = create_app(
                include_pty=False,
                include_stream=False,
                include_sandbox=False,
                include_companion=False,
            )

        client = TestClient(app)
        # In parity mode, /internal/v1/* is NOT mounted in-process
        response = client.get("/internal/v1/files/list", params={"path": "."})
        assert response.status_code == 404

    def test_parity_mode_stores_url_on_state(self, tmp_path):
        """Parity mode stores parity URL on app.state."""
        with patch.dict("os.environ", {
            "WORKSPACE_ROOT": str(tmp_path),
            "BORING_UI_RUN_MODE": "local",
            "LOCAL_PARITY_MODE": "http",
            "LOCAL_PARITY_PORT": "9999",
        }):
            from boring_ui.api.app import create_app
            app = create_app(
                include_pty=False,
                include_stream=False,
                include_sandbox=False,
                include_companion=False,
            )

        assert app.state.local_parity_url == "http://127.0.0.1:9999"

    def test_parity_mode_health_still_works(self, tmp_path):
        """Health endpoint works in parity mode."""
        with patch.dict("os.environ", {
            "WORKSPACE_ROOT": str(tmp_path),
            "BORING_UI_RUN_MODE": "local",
            "LOCAL_PARITY_MODE": "http",
        }):
            from boring_ui.api.app import create_app
            app = create_app(
                include_pty=False,
                include_stream=False,
                include_sandbox=False,
                include_companion=False,
            )

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200


class TestParityModeSecurityInvariants:
    """bd-1adh.7.3: Parity mode preserves security invariants."""

    def test_standalone_local_api_rejects_unauthenticated(self, tmp_path):
        """Standalone local-api rejects unauthenticated requests (401).

        Without capability auth middleware, @require_capability decorators
        reject requests before path validation even runs.
        """
        from boring_ui.api.local_api.app import create_local_api_app

        app = create_local_api_app(tmp_path)
        client = TestClient(app)

        response = client.get(
            "/internal/v1/files/read",
            params={"path": "anything.txt"},
        )
        assert response.status_code == 401

    def test_standalone_local_api_health_public(self, tmp_path):
        """Standalone local-api health endpoint is public (no auth)."""
        from boring_ui.api.local_api.app import create_local_api_app

        app = create_local_api_app(tmp_path)
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200

    def test_path_traversal_blocked_when_authed(self, tmp_path):
        """Path traversal blocked even with valid capability context.

        Uses the full control-plane app (LOCAL mode, in-process) which
        auto-injects capability context. Path validation still blocks
        escaping the workspace.
        """
        with patch.dict("os.environ", {
            "WORKSPACE_ROOT": str(tmp_path),
            "BORING_UI_RUN_MODE": "local",
        }):
            import os
            os.environ.pop("LOCAL_PARITY_MODE", None)
            from boring_ui.api.app import create_app
            app = create_app(
                include_pty=False,
                include_stream=False,
                include_sandbox=False,
                include_companion=False,
            )

        client = TestClient(app)
        response = client.get(
            "/internal/v1/files/read",
            params={"path": "../../../etc/passwd"},
        )
        assert response.status_code == 403
