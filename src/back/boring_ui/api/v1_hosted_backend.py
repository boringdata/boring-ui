"""HOSTED mode backend adapters for canonical v1 API (bd-1pwb.6.1).

Wraps the hosted sandbox client to conform to V1 protocol interfaces.
All operations are proxied to the internal sandbox service with capability
token injection.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from .contracts import (
    FileInfo,
    ListFilesResponse,
    ReadFileResponse,
    WriteFileResponse,
    GitStatusResponse,
    GitDiffResponse,
    GitShowResponse,
    ExecRunRequest,
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
