"""Tests for canonical /api/v1 router and contracts (bd-1pwb.6.1).

Verifies:
- V1 routes serve correct response shapes per contracts.py DTOs
- LOCAL mode backend adapters produce valid contract responses
- Missing backends return 501
- Response model validation catches shape drift
"""

import pytest
from unittest.mock import patch
from pathlib import Path
from fastapi.testclient import TestClient

from boring_ui.api.contracts import (
    ListFilesResponse,
    ReadFileResponse,
    WriteFileResponse,
    DeleteFileResponse,
    RenameFileResponse,
    MoveFileResponse,
    SearchFilesResponse,
    GitStatusResponse,
    GitDiffResponse,
    GitShowResponse,
)


def _make_local_v1_app(tmp_path):
    """Create a LOCAL-mode app with v1 routes."""
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


class TestV1FilesLocalMode:
    """V1 files routes in LOCAL mode."""

    def test_list_files_returns_contract_shape(self, tmp_path):
        (tmp_path / "hello.txt").write_text("world")
        (tmp_path / "subdir").mkdir()
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/files/list", params={"path": "."})
        assert resp.status_code == 200
        data = resp.json()

        # Validate against contract
        parsed = ListFilesResponse(**data)
        assert parsed.path == "."
        assert len(parsed.files) == 2

        names = {f.name for f in parsed.files}
        assert "hello.txt" in names
        assert "subdir" in names

        for f in parsed.files:
            if f.name == "subdir":
                assert f.type == "dir"
            else:
                assert f.type == "file"

    def test_read_file_returns_contract_shape(self, tmp_path):
        (tmp_path / "test.txt").write_text("content here")
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/files/read", params={"path": "test.txt"})
        assert resp.status_code == 200
        data = resp.json()

        parsed = ReadFileResponse(**data)
        assert parsed.content == "content here"
        assert parsed.path == "test.txt"
        assert parsed.size == 12

    def test_write_file_returns_contract_shape(self, tmp_path):
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/files/write",
            json={"path": "new.txt", "content": "new content"},
        )
        assert resp.status_code == 200
        data = resp.json()

        parsed = WriteFileResponse(**data)
        assert parsed.path == "new.txt"
        assert parsed.size == 11
        assert parsed.written is True

        # Verify file was actually written
        assert (tmp_path / "new.txt").read_text() == "new content"

    def test_read_file_not_found_returns_404(self, tmp_path):
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/files/read", params={"path": "missing.txt"})
        assert resp.status_code == 404

    def test_delete_file_returns_contract_shape(self, tmp_path):
        (tmp_path / "deleteme.txt").write_text("gone")
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.delete("/api/v1/files/delete", params={"path": "deleteme.txt"})
        assert resp.status_code == 200
        data = resp.json()

        parsed = DeleteFileResponse(**data)
        assert parsed.path == "deleteme.txt"
        assert parsed.deleted is True
        assert not (tmp_path / "deleteme.txt").exists()

    def test_rename_file_returns_contract_shape(self, tmp_path):
        (tmp_path / "old.txt").write_text("x")
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/files/rename",
            json={"old_path": "old.txt", "new_path": "new.txt"},
        )
        assert resp.status_code == 200
        data = resp.json()

        parsed = RenameFileResponse(**data)
        assert parsed.old_path == "old.txt"
        assert parsed.new_path == "new.txt"
        assert parsed.renamed is True
        assert not (tmp_path / "old.txt").exists()
        assert (tmp_path / "new.txt").exists()

    def test_move_file_returns_contract_shape(self, tmp_path):
        (tmp_path / "src.txt").write_text("x")
        (tmp_path / "dest").mkdir()
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/files/move",
            json={"src_path": "src.txt", "dest_dir": "dest"},
        )
        assert resp.status_code == 200
        data = resp.json()

        parsed = MoveFileResponse(**data)
        assert parsed.src_path == "src.txt"
        assert parsed.dest_path == "dest/src.txt"
        assert parsed.moved is True
        assert not (tmp_path / "src.txt").exists()
        assert (tmp_path / "dest" / "src.txt").exists()

    def test_search_files_returns_contract_shape(self, tmp_path):
        (tmp_path / "alpha.py").write_text("print('a')")
        (tmp_path / "beta.txt").write_text("b")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "gamma.py").write_text("print('g')")
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/files/search", params={"q": "*.py", "path": "."})
        assert resp.status_code == 200
        data = resp.json()

        parsed = SearchFilesResponse(**data)
        assert parsed.pattern == "*.py"
        names = {entry.name for entry in parsed.results}
        assert names == {"alpha.py", "gamma.py"}


class TestV1GitLocalMode:
    """V1 git routes in LOCAL mode."""

    def _init_git(self, tmp_path):
        """Initialize a git repo in tmp_path."""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path, capture_output=True,
        )
        (tmp_path / ".gitkeep").write_text("")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path, capture_output=True,
        )

    def test_git_status_returns_contract_shape(self, tmp_path):
        self._init_git(tmp_path)
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/git/status")
        assert resp.status_code == 200
        data = resp.json()

        parsed = GitStatusResponse(**data)
        assert parsed.is_repo is True
        assert isinstance(parsed.files, dict)

    def test_git_diff_returns_contract_shape(self, tmp_path):
        self._init_git(tmp_path)
        (tmp_path / "changed.txt").write_text("modified")
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/git/diff", params={"path": "changed.txt"})
        assert resp.status_code == 200
        data = resp.json()

        parsed = GitDiffResponse(**data)
        assert parsed.path == "changed.txt"
        assert isinstance(parsed.diff, str)

    def test_git_show_returns_contract_shape(self, tmp_path):
        self._init_git(tmp_path)
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/git/show", params={"path": ".gitkeep"})
        assert resp.status_code == 200
        data = resp.json()

        parsed = GitShowResponse(**data)
        assert parsed.path == ".gitkeep"
        assert parsed.is_new is False

    def test_git_show_untracked_file(self, tmp_path):
        self._init_git(tmp_path)
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.get("/api/v1/git/show", params={"path": "nonexistent.txt"})
        assert resp.status_code == 200
        data = resp.json()

        parsed = GitShowResponse(**data)
        assert parsed.content is None
        assert parsed.is_new is True


class TestV1MissingBackend:
    """Routes return 501 when backend is not provided."""

    def test_exec_not_available_in_local(self, tmp_path):
        """LOCAL mode has no exec backend on v1."""
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        resp = client.post(
            "/api/v1/exec/run",
            json={"command": "ls", "timeout_seconds": 5},
        )
        assert resp.status_code == 501


class TestV1ContractParity:
    """Verify v1 and legacy routes return compatible data."""

    def test_list_files_parity(self, tmp_path):
        """V1 list_files and legacy /api/tree return same directory contents."""
        (tmp_path / "a.txt").write_text("aaa")
        (tmp_path / "b").mkdir()
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        legacy = client.get("/api/tree", params={"path": "."}).json()
        v1 = client.get("/api/v1/files/list", params={"path": "."}).json()

        legacy_names = {e["name"] for e in legacy["entries"]}
        v1_names = {f["name"] for f in v1["files"]}
        assert legacy_names == v1_names

    def test_read_file_parity(self, tmp_path):
        """V1 read_file and legacy /api/file return same content."""
        (tmp_path / "test.txt").write_text("parity test")
        app = _make_local_v1_app(tmp_path)
        client = TestClient(app)

        legacy = client.get("/api/file", params={"path": "test.txt"}).json()
        v1 = client.get("/api/v1/files/read", params={"path": "test.txt"}).json()

        assert legacy["content"] == v1["content"]
        assert legacy["path"] == v1["path"]
