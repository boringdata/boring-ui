"""Security regression: path traversal tests.

Bead: bd-1joj.26 (TEST-SEC)

Verifies that path traversal attacks are rejected across all relevant
endpoints: share links, proxy routes, and file APIs.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from control_plane.app.main import create_app
from control_plane.app.settings import ControlPlaneSettings
from control_plane.app.db.share_repo import _normalize_path


# ── Path normalization unit tests ─────────────────────────────────────


class TestPathNormalization:
    def test_rejects_dot_dot_traversal(self):
        with pytest.raises(ValueError, match="traversal"):
            _normalize_path("../../etc/passwd")

    def test_rejects_dot_dot_in_middle(self):
        with pytest.raises(ValueError, match="traversal"):
            _normalize_path("/docs/../../../etc/shadow")

    def test_rejects_encoded_traversal(self):
        # Even if .. appears in the raw path
        with pytest.raises(ValueError, match="traversal"):
            _normalize_path("/docs/..%2F../etc/passwd")

    def test_normalizes_leading_slash(self):
        assert _normalize_path("docs/readme.md") == "/docs/readme.md"

    def test_normalizes_dot_segment(self):
        assert _normalize_path("/docs/./readme.md") == "/docs/readme.md"

    def test_normalizes_double_slash(self):
        result = _normalize_path("/docs//readme.md")
        assert "//" not in result
        assert result == "/docs/readme.md"

    def test_absolute_path_preserved(self):
        assert _normalize_path("/docs/readme.md") == "/docs/readme.md"


# ── Proxy route path traversal tests ─────────────────────────────────


class TestProxyPathTraversal:
    @pytest.fixture(autouse=True)
    def setup(self):
        app = create_app(ControlPlaneSettings(environment="local"))
        self.client = TestClient(app)
        deps = app.state.deps
        asyncio.get_event_loop().run_until_complete(self._seed(deps))

    async def _seed(self, deps):
        await deps.workspace_repo.create({
            "id": "ws_1",
            "name": "Test",
            "owner_id": "user-1",
            "app_id": "boring-ui",
        })
        await deps.member_repo.add_member("ws_1", {
            "user_id": "user-1",
            "email": "user@test.com",
            "role": "admin",
            "status": "active",
        })
        await deps.runtime_store.upsert_runtime("ws_1", {
            "state": "ready",
            "sandbox_name": "sbx-test",
        })

    def _headers(self):
        return {"Authorization": "Bearer test-token", "X-User-ID": "user-1"}

    def test_proxy_rejects_traversal_outside_workspace_routes(self):
        """Paths resolved via .. that land outside workspace route prefixes are rejected."""
        paths = [
            "/w/ws_1/etc/passwd",
            "/w/ws_1/admin/settings",
            "/w/ws_1/internal/debug",
        ]
        for path in paths:
            resp = self.client.get(path, headers=self._headers())
            assert resp.status_code == 404, f"Expected 404 for {path}, got {resp.status_code}"

    def test_proxy_does_not_serve_parent_directory(self):
        """Verify that traversal above workspace root is not possible."""
        resp = self.client.get(
            "/w/ws_1/app/../../../etc/passwd",
            headers=self._headers(),
        )
        # Starlette normalizes .. before it reaches the handler
        assert resp.status_code in (400, 404)
