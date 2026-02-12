"""Tests for deprecation signaling middleware (bd-1pwb.6.2).

Verifies:
- Legacy routes get Deprecation, Sunset, and Link headers
- Canonical v1 routes do NOT get deprecation headers
- Health endpoint is not deprecated
- Link header points to correct canonical endpoint
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


def _make_app(tmp_path):
    """Create LOCAL-mode app with deprecation middleware."""
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


class TestDeprecationHeaders:
    """Verify deprecation headers on legacy routes."""

    def test_legacy_tree_has_deprecation_header(self, tmp_path):
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/tree", params={"path": "."})
        assert resp.headers.get("Deprecation") == "true"

    def test_legacy_tree_has_sunset_header(self, tmp_path):
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/tree", params={"path": "."})
        assert "Sunset" in resp.headers

    def test_legacy_tree_has_link_header(self, tmp_path):
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/tree", params={"path": "."})
        link = resp.headers.get("Link", "")
        assert "/api/v1/files/list" in link
        assert 'rel="successor-version"' in link

    def test_legacy_file_deprecated(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/file", params={"path": "a.txt"})
        assert resp.headers.get("Deprecation") == "true"
        assert "/api/v1/files/read" in resp.headers.get("Link", "")

    def test_legacy_git_status_deprecated(self, tmp_path):
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/git/status")
        assert resp.headers.get("Deprecation") == "true"
        assert "/api/v1/git/status" in resp.headers.get("Link", "")

    def test_legacy_git_diff_deprecated(self, tmp_path):
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/git/diff", params={"path": "x.txt"})
        assert resp.headers.get("Deprecation") == "true"
        assert "/api/v1/git/diff" in resp.headers.get("Link", "")


class TestNoDeprecationOnCanonical:
    """Canonical v1 routes must NOT have deprecation headers."""

    def test_v1_files_list_not_deprecated(self, tmp_path):
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/v1/files/list", params={"path": "."})
        assert resp.headers.get("Deprecation") is None

    def test_v1_files_read_not_deprecated(self, tmp_path):
        (tmp_path / "a.txt").write_text("x")
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/v1/files/read", params={"path": "a.txt"})
        assert resp.headers.get("Deprecation") is None

    def test_v1_git_status_not_deprecated(self, tmp_path):
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/api/v1/git/status")
        assert resp.headers.get("Deprecation") is None

    def test_health_not_deprecated(self, tmp_path):
        app = _make_app(tmp_path)
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.headers.get("Deprecation") is None
