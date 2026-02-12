"""LOCAL mode backend adapters for canonical v1 API (bd-1pwb.6.1).

Wraps existing FileService and GitService to conform to the V1 protocol
interfaces. All operations are in-process — no HTTP round-trips.
"""

from __future__ import annotations

from .contracts import (
    FileInfo,
    ListFilesResponse,
    ReadFileResponse,
    WriteFileResponse,
    DeleteFileResponse,
    RenameFileResponse,
    MoveFileResponse,
    SearchFilesResponse,
    SearchFileResult,
    GitStatusResponse,
    GitDiffResponse,
    GitShowResponse,
)
from .modules.files.service import FileService
from .modules.git.service import GitService


class LocalFilesBackend:
    """V1FilesBackend adapter for LOCAL mode."""

    def __init__(self, file_service: FileService):
        self._svc = file_service

    async def v1_list_files(self, path: str) -> ListFilesResponse:
        result = self._svc.list_directory(path)
        entries = []
        for entry in result.get("entries", []):
            entries.append(FileInfo(
                name=entry["name"],
                type="dir" if entry.get("is_dir") else "file",
                size=entry.get("size"),
            ))
        return ListFilesResponse(files=entries, path=result["path"])

    async def v1_read_file(self, path: str) -> ReadFileResponse:
        result = self._svc.read_file(path)
        content = result["content"]
        return ReadFileResponse(
            content=content,
            path=result["path"],
            size=len(content),
        )

    async def v1_write_file(self, path: str, content: str) -> WriteFileResponse:
        self._svc.write_file(path, content)
        return WriteFileResponse(path=path, size=len(content), written=True)

    async def v1_delete_file(self, path: str) -> DeleteFileResponse:
        result = self._svc.delete_file(path)
        return DeleteFileResponse(
            path=result.get("path", path),
            deleted=bool(result.get("success", True)),
        )

    async def v1_rename_file(self, old_path: str, new_path: str) -> RenameFileResponse:
        result = self._svc.rename_file(old_path, new_path)
        return RenameFileResponse(
            old_path=result.get("old_path", old_path),
            new_path=result.get("new_path", new_path),
            renamed=bool(result.get("success", True)),
        )

    async def v1_move_file(self, src_path: str, dest_dir: str) -> MoveFileResponse:
        result = self._svc.move_file(src_path, dest_dir)
        return MoveFileResponse(
            src_path=result.get("old_path", src_path),
            dest_path=result.get("dest_path", src_path),
            moved=bool(result.get("success", True)),
        )

    async def v1_search_files(self, pattern: str, path: str = ".") -> SearchFilesResponse:
        result = self._svc.search_files(pattern, path)
        entries = [
            SearchFileResult(
                name=item.get("name", ""),
                path=item.get("path", ""),
                dir=item.get("dir", ""),
            )
            for item in result.get("results", [])
        ]
        return SearchFilesResponse(
            results=entries,
            pattern=result.get("pattern", pattern),
            path=result.get("path", path),
        )


class LocalGitBackend:
    """V1GitBackend adapter for LOCAL mode."""

    def __init__(self, git_service: GitService):
        self._svc = git_service

    async def v1_git_status(self) -> GitStatusResponse:
        result = self._svc.get_status()
        files = result.get("files", {})
        if isinstance(files, list):
            files = {}
        return GitStatusResponse(
            is_repo=result.get("is_repo", False),
            files=files,
        )

    async def v1_git_diff(self, path: str) -> GitDiffResponse:
        result = self._svc.get_diff(path)
        return GitDiffResponse(
            diff=result.get("diff", ""),
            path=result.get("path", path),
        )

    async def v1_git_show(self, path: str) -> GitShowResponse:
        result = self._svc.get_show(path)
        return GitShowResponse(
            content=result.get("content"),
            path=result.get("path", path),
            is_new=result.get("content") is None,
        )
