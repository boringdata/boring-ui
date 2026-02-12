"""HOSTED mode backend adapters for canonical v1 API (bd-1pwb.6.1).

Wraps the hosted sandbox client to conform to V1 protocol interfaces.
All operations are proxied to the internal sandbox service with capability
token injection.
"""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

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
    ExecRunResponse,
)


class HostedFilesBackend:
    """V1FilesBackend adapter for HOSTED mode."""

    def __init__(self, client, capability_issuer):
        self._client = client
        self._issuer = capability_issuer

    def _issue_token(self, operations: set[str]) -> str:
        return self._issuer.issue_token(
            workspace_id="default",
            operations=operations,
            ttl_seconds=60,
        )

    async def v1_list_files(self, path: str) -> ListFilesResponse:
        token = self._issue_token({"files:list"})
        data = await self._client.list_files(path, capability_token=token)
        entries = []
        for item in data.get("files", []):
            name = item.get("name", "")
            is_dir = item.get("type") == "dir"
            rel_path = str(PurePosixPath(path) / name) if path != "." else name
            entries.append(FileInfo(
                name=name,
                type="dir" if is_dir else "file",
                size=item.get("size"),
            ))
        return ListFilesResponse(files=entries, path=path)

    async def v1_read_file(self, path: str) -> ReadFileResponse:
        token = self._issue_token({"files:read"})
        data = await self._client.read_file(path, capability_token=token)
        content = data.get("content", "")
        return ReadFileResponse(
            content=content,
            path=data.get("path", path),
            size=data.get("size", len(content)),
        )

    async def v1_write_file(self, path: str, content: str) -> WriteFileResponse:
        token = self._issue_token({"files:write"})
        data = await self._client.write_file(path, content, capability_token=token)
        return WriteFileResponse(
            path=data.get("path", path),
            size=data.get("size", len(content)),
            written=data.get("written", True),
        )

    async def v1_delete_file(self, path: str) -> DeleteFileResponse:
        token = self._issue_token({"files:write"})
        data = await self._client.delete_file(path, capability_token=token)
        return DeleteFileResponse(
            path=data.get("path", path),
            deleted=data.get("deleted", data.get("success", True)),
        )

    async def v1_rename_file(self, old_path: str, new_path: str) -> RenameFileResponse:
        token = self._issue_token({"files:write"})
        data = await self._client.rename_file(old_path, new_path, capability_token=token)
        return RenameFileResponse(
            old_path=data.get("old_path", old_path),
            new_path=data.get("new_path", new_path),
            renamed=data.get("renamed", data.get("success", True)),
        )

    async def v1_move_file(self, src_path: str, dest_dir: str) -> MoveFileResponse:
        token = self._issue_token({"files:write"})
        data = await self._client.move_file(src_path, dest_dir, capability_token=token)
        return MoveFileResponse(
            src_path=data.get("src_path", data.get("old_path", src_path)),
            dest_path=data.get("dest_path", src_path),
            moved=data.get("moved", data.get("success", True)),
        )

    async def v1_search_files(self, pattern: str, path: str = ".") -> SearchFilesResponse:
        token = self._issue_token({"files:list"})
        results: list[SearchFileResult] = []

        async def walk(dir_path: str, depth: int = 0) -> None:
            if depth > 10:
                return
            listing = await self._client.list_files(dir_path, capability_token=token)
            for item in listing.get("files", []):
                name = item.get("name", "")
                rel_path = str(PurePosixPath(dir_path) / name) if dir_path != "." else name
                parent_dir = str(PurePosixPath(rel_path).parent)
                if parent_dir == ".":
                    parent_dir = ""

                if fnmatch.fnmatch(name.lower(), pattern.lower()):
                    results.append(
                        SearchFileResult(name=name, path=rel_path, dir=parent_dir)
                    )

                if item.get("type") == "dir":
                    await walk(rel_path, depth + 1)

        await walk(path)
        return SearchFilesResponse(results=results, pattern=pattern, path=path)


class HostedGitBackend:
    """V1GitBackend adapter for HOSTED mode."""

    def __init__(self, client, capability_issuer):
        self._client = client
        self._issuer = capability_issuer

    def _issue_token(self, operations: set[str]) -> str:
        return self._issuer.issue_token(
            workspace_id="default",
            operations=operations,
            ttl_seconds=60,
        )

    async def v1_git_status(self) -> GitStatusResponse:
        token = self._issue_token({"git:status"})
        data = await self._client.git_status(capability_token=token)
        files: dict[str, str] = {}
        for p in data.get("staged", []):
            files[p] = "M"
        for p in data.get("unstaged", []):
            files[p] = "M"
        for p in data.get("untracked", []):
            files[p] = "U"
        return GitStatusResponse(
            is_repo=data.get("is_repo", True),
            files=files,
        )

    async def v1_git_diff(self, path: str) -> GitDiffResponse:
        token = self._issue_token({"git:diff"})
        data = await self._client.git_diff("working", capability_token=token)
        full_diff = data.get("diff", "") or ""
        marker = f"diff --git a/{path} b/{path}"
        if marker not in full_diff:
            return GitDiffResponse(diff="", path=path)
        chunks = full_diff.split("diff --git ")
        matched = ""
        for chunk in chunks:
            if chunk.startswith(f"a/{path} b/{path}"):
                matched = "diff --git " + chunk
                break
        return GitDiffResponse(diff=matched, path=path)

    async def v1_git_show(self, path: str) -> GitShowResponse:
        token = self._issue_token({"files:read"})
        try:
            data = await self._client.read_file(path, capability_token=token)
            return GitShowResponse(
                content=data.get("content"),
                path=path,
                is_new=False,
            )
        except Exception:
            return GitShowResponse(content=None, path=path, is_new=True)


class HostedExecBackend:
    """V1ExecBackend adapter for HOSTED mode."""

    def __init__(self, client, capability_issuer):
        self._client = client
        self._issuer = capability_issuer

    def _issue_token(self, operations: set[str]) -> str:
        return self._issuer.issue_token(
            workspace_id="default",
            operations=operations,
            ttl_seconds=60,
        )

    async def v1_exec_run(self, command: str, timeout_seconds: int) -> ExecRunResponse:
        timeout = min(max(timeout_seconds, 1), 300)
        token = self._issue_token({"exec:run"})
        data = await self._client.exec_run(
            command, timeout, capability_token=token,
        )
        return ExecRunResponse(
            command=data.get("command", command),
            exit_code=data.get("exit_code", -1),
            timeout_seconds=data.get("timeout_seconds", timeout),
            status=data.get("status", "completed"),
            stdout=data.get("stdout"),
            stderr=data.get("stderr"),
            truncated=data.get("truncated", False),
        )
