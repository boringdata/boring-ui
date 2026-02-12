"""Canonical /api/v1 router for files, git, and exec operations (bd-1pwb.6.1).

Provides a single set of versioned routes that work identically in LOCAL and
HOSTED modes. The backend is pluggable via a protocol interface:

- LOCAL mode: delegates to FileService + GitService (in-process)
- HOSTED mode: delegates to hosted client (proxied via capability tokens)

Response shapes conform to contracts.py DTOs.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from fastapi import APIRouter, HTTPException, Request, status

from .contracts import (
    ListFilesResponse,
    ReadFileResponse,
    WriteFileRequest,
    WriteFileResponse,
    GitStatusResponse,
    GitDiffResponse,
    GitShowResponse,
    ExecRunRequest,
    ExecRunResponse,
    FileInfo,
)


@runtime_checkable
class V1FilesBackend(Protocol):
    """Backend interface for file operations."""

    async def v1_list_files(self, path: str) -> ListFilesResponse: ...
    async def v1_read_file(self, path: str) -> ReadFileResponse: ...
    async def v1_write_file(self, path: str, content: str) -> WriteFileResponse: ...


@runtime_checkable
class V1GitBackend(Protocol):
    """Backend interface for git operations."""

    async def v1_git_status(self) -> GitStatusResponse: ...
    async def v1_git_diff(self, path: str) -> GitDiffResponse: ...
    async def v1_git_show(self, path: str) -> GitShowResponse: ...


@runtime_checkable
class V1ExecBackend(Protocol):
    """Backend interface for exec operations."""

    async def v1_exec_run(self, command: str, timeout_seconds: int) -> ExecRunResponse: ...


def create_v1_router(
    files_backend: V1FilesBackend | None = None,
    git_backend: V1GitBackend | None = None,
    exec_backend: V1ExecBackend | None = None,
) -> APIRouter:
    """Create canonical v1 API router.

    At least one backend must be provided. Routes for missing backends
    return 501 Not Implemented.
    """
    router = APIRouter(tags=["v1"])

    # ─── Files ────────────────────────────────────────────────────

    @router.get("/files/list", response_model=ListFilesResponse)
    async def list_files(path: str = "."):
        if files_backend is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Files not available")
        return await files_backend.v1_list_files(path)

    @router.get("/files/read", response_model=ReadFileResponse)
    async def read_file(path: str):
        if files_backend is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Files not available")
        return await files_backend.v1_read_file(path)

    @router.post("/files/write", response_model=WriteFileResponse)
    async def write_file(body: WriteFileRequest):
        if files_backend is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Files not available")
        return await files_backend.v1_write_file(body.path, body.content)

    # ─── Git ──────────────────────────────────────────────────────

    @router.get("/git/status", response_model=GitStatusResponse)
    async def git_status():
        if git_backend is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Git not available")
        return await git_backend.v1_git_status()

    @router.get("/git/diff", response_model=GitDiffResponse)
    async def git_diff(path: str):
        if git_backend is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Git not available")
        return await git_backend.v1_git_diff(path)

    @router.get("/git/show", response_model=GitShowResponse)
    async def git_show(path: str):
        if git_backend is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Git not available")
        return await git_backend.v1_git_show(path)

    # ─── Exec ─────────────────────────────────────────────────────

    @router.post("/exec/run", response_model=ExecRunResponse)
    async def exec_run(body: ExecRunRequest):
        if exec_backend is None:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Exec not available")
        return await exec_backend.v1_exec_run(body.command, body.timeout_seconds)

    return router
