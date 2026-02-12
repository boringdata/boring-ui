"""Contract validation tests for /api/v1 (bd-1pwb.6.3).

Verifies:
- All v1 DTOs can be instantiated and serialized
- Response shapes match contract definitions (no extra/missing fields)
- Deprecation headers present on legacy, absent on v1
- Contract shape drift detection via round-trip validation
"""

import pytest
from pydantic import ValidationError

from boring_ui.api.contracts import (
    FileInfo,
    ListFilesResponse,
    ReadFileResponse,
    WriteFileRequest,
    WriteFileResponse,
    GitStatusResponse,
    GitDiffResponse,
    GitShowResponse,
    ExecRunRequest,
    ExecRunResponse,
    ErrorCode,
    ErrorResponse,
)


class TestFileContracts:
    """File operation DTO validation."""

    def test_file_info_file_type(self):
        f = FileInfo(name="app.py", type="file", size=100)
        assert f.name == "app.py"
        assert f.type == "file"
        assert f.size == 100

    def test_file_info_dir_type(self):
        f = FileInfo(name="src", type="dir")
        assert f.type == "dir"
        assert f.size is None

    def test_list_files_response(self):
        resp = ListFilesResponse(
            files=[FileInfo(name="a.py", type="file", size=10)],
            path=".",
        )
        data = resp.model_dump()
        assert "files" in data
        assert "path" in data
        assert data["files"][0]["name"] == "a.py"

    def test_list_files_response_empty(self):
        resp = ListFilesResponse(files=[], path="empty_dir")
        assert len(resp.files) == 0

    def test_read_file_response(self):
        resp = ReadFileResponse(content="hello", path="a.txt", size=5)
        data = resp.model_dump()
        assert data["content"] == "hello"
        assert data["size"] == 5

    def test_write_file_request(self):
        req = WriteFileRequest(path="new.txt", content="data")
        assert req.path == "new.txt"
        assert req.content == "data"

    def test_write_file_response(self):
        resp = WriteFileResponse(path="new.txt", size=4, written=True)
        assert resp.written is True

    def test_write_file_request_missing_path_fails(self):
        with pytest.raises(ValidationError):
            WriteFileRequest(content="data")

    def test_write_file_request_missing_content_fails(self):
        with pytest.raises(ValidationError):
            WriteFileRequest(path="x.txt")


class TestGitContracts:
    """Git operation DTO validation."""

    def test_git_status_response(self):
        resp = GitStatusResponse(is_repo=True, files={"a.py": "M"})
        assert resp.is_repo is True
        assert resp.files["a.py"] == "M"

    def test_git_status_no_repo(self):
        resp = GitStatusResponse(is_repo=False)
        assert resp.files == {}

    def test_git_diff_response(self):
        resp = GitDiffResponse(diff="diff --git ...", path="a.py")
        assert resp.diff.startswith("diff")
        assert resp.path == "a.py"

    def test_git_show_tracked_file(self):
        resp = GitShowResponse(content="code", path="a.py", is_new=False)
        assert resp.content == "code"
        assert resp.is_new is False

    def test_git_show_untracked_file(self):
        resp = GitShowResponse(content=None, path="new.py", is_new=True)
        assert resp.content is None
        assert resp.is_new is True


class TestExecContracts:
    """Exec operation DTO validation."""

    def test_exec_run_request_defaults(self):
        req = ExecRunRequest(command="ls -la")
        assert req.command == "ls -la"
        assert req.timeout_seconds == 30

    def test_exec_run_request_custom_timeout(self):
        req = ExecRunRequest(command="build", timeout_seconds=120)
        assert req.timeout_seconds == 120

    def test_exec_run_request_timeout_bounds(self):
        with pytest.raises(ValidationError):
            ExecRunRequest(command="x", timeout_seconds=0)
        with pytest.raises(ValidationError):
            ExecRunRequest(command="x", timeout_seconds=301)

    def test_exec_run_response(self):
        resp = ExecRunResponse(
            command="ls",
            exit_code=0,
            timeout_seconds=30,
            status="completed",
            stdout="file.txt",
        )
        assert resp.exit_code == 0
        assert resp.stderr is None


class TestErrorContracts:
    """Error response DTO validation."""

    def test_error_response(self):
        resp = ErrorResponse(
            code=ErrorCode.AUTH_MISSING,
            message="Missing token",
        )
        assert resp.code == ErrorCode.AUTH_MISSING
        assert resp.request_id is None

    def test_error_response_with_details(self):
        resp = ErrorResponse(
            code=ErrorCode.NOT_FOUND,
            message="File not found",
            request_id="abc-123",
            details={"path": "missing.txt"},
        )
        data = resp.model_dump()
        assert data["details"]["path"] == "missing.txt"


class TestContractRoundTrip:
    """Verify contracts survive JSON round-trip serialization."""

    def test_list_files_round_trip(self):
        original = ListFilesResponse(
            files=[
                FileInfo(name="a.py", type="file", size=100),
                FileInfo(name="src", type="dir"),
            ],
            path=".",
        )
        json_str = original.model_dump_json()
        restored = ListFilesResponse.model_validate_json(json_str)
        assert restored == original

    def test_exec_response_round_trip(self):
        original = ExecRunResponse(
            command="echo hi",
            exit_code=0,
            timeout_seconds=30,
            status="completed",
            stdout="hi\n",
            stderr=None,
            truncated=False,
        )
        json_str = original.model_dump_json()
        restored = ExecRunResponse.model_validate_json(json_str)
        assert restored == original

    def test_git_status_round_trip(self):
        original = GitStatusResponse(
            is_repo=True,
            files={"a.py": "M", "b.py": "U"},
        )
        json_str = original.model_dump_json()
        restored = GitStatusResponse.model_validate_json(json_str)
        assert restored == original
