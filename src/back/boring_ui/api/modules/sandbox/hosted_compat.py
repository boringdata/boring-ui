"""Hosted compatibility routes for existing frontend API paths.

These routes keep legacy frontend endpoints working in hosted mode by mapping:
- /api/tree, /api/file, /api/search
- /api/git/status, /api/git/diff, /api/git/show

to sandbox-backed operations through HostedSandboxClient.
"""

from __future__ import annotations

import fnmatch
from collections import deque
from pathlib import PurePosixPath
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from .hosted_client import HostedSandboxClient
from ...auth_middleware import get_auth_context, require_permission
from ...capability_tokens import CapabilityTokenIssuer


class FileContent(BaseModel):
    content: str


def create_hosted_compat_router(
    client: HostedSandboxClient,
    capability_issuer: CapabilityTokenIssuer,
) -> APIRouter:
    router = APIRouter(tags=["hosted-compat"])

    def _issue_token(request: Request, operations: set[str]) -> str:
        auth = get_auth_context(request)
        workspace_id = auth.workspace_id or "default"
        return capability_issuer.issue_token(
            workspace_id=workspace_id,
            operations=operations,
            ttl_seconds=60,
        )

    def _join_rel(base: str, name: str) -> str:
        base_clean = (base or ".").strip()
        if base_clean in {"", "."}:
            return name
        return str(PurePosixPath(base_clean) / name)

    def _map_tree(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        files = payload.get("files", [])
        entries = []
        for item in files:
            name = item.get("name", "")
            is_dir = item.get("type") == "dir"
            entries.append(
                {
                    "name": name,
                    "path": _join_rel(path, name),
                    "is_dir": is_dir,
                    "size": item.get("size"),
                }
            )
        return {"entries": entries, "path": path}

    @router.get("/tree")
    @require_permission("files:read")
    async def get_tree(request: Request, path: str = "."):
        try:
            token = _issue_token(request, {"files:list"})
            data = await client.list_files(path, capability_token=token)
            return _map_tree(path, data)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Sandbox tree failed: {exc}")

    @router.get("/file")
    @require_permission("files:read")
    async def get_file(request: Request, path: str):
        try:
            token = _issue_token(request, {"files:read"})
            data = await client.read_file(path, capability_token=token)
            return {"content": data.get("content", ""), "path": path}
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Sandbox read failed: {exc}")

    @router.put("/file")
    @require_permission("files:write")
    async def put_file(request: Request, path: str, body: FileContent):
        try:
            token = _issue_token(request, {"files:write"})
            await client.write_file(path, body.content, capability_token=token)
            return {"success": True, "path": path}
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Sandbox write failed: {exc}")

    @router.get("/search")
    @require_permission("files:read")
    async def search_files(
        request: Request,
        q: str = Query(..., min_length=1),
        path: str = ".",
    ):
        # Lightweight BFS search over list_files; sufficient for hosted-dev compat.
        token = _issue_token(request, {"files:list"})
        pattern = q.strip()
        if not pattern:
            return {"results": [], "pattern": q, "path": path}
        queue: deque[tuple[str, int]] = deque([(path, 0)])
        max_depth = 8
        max_dirs = 500
        visited = 0
        results: list[dict[str, str]] = []

        try:
            while queue and visited < max_dirs:
                current, depth = queue.popleft()
                visited += 1
                payload = await client.list_files(current, capability_token=token)
                for item in payload.get("files", []):
                    name = item.get("name", "")
                    full_path = _join_rel(current, name)
                    if fnmatch.fnmatch(name.lower(), pattern.lower()):
                        parent = str(PurePosixPath(full_path).parent)
                        results.append(
                            {
                                "name": name,
                                "path": full_path,
                                "dir": "" if parent == "." else parent,
                            }
                        )
                    if item.get("type") == "dir" and depth < max_depth:
                        queue.append((full_path, depth + 1))
            return {"results": results, "pattern": q, "path": path}
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Sandbox search failed: {exc}")

    @router.get("/git/status")
    @require_permission("git:read")
    async def git_status(request: Request):
        try:
            token = _issue_token(request, {"git:status"})
            data = await client.git_status(capability_token=token)
            files: dict[str, str] = {}
            for p in data.get("staged", []):
                files[p] = "M"
            for p in data.get("unstaged", []):
                files[p] = "M"
            for p in data.get("untracked", []):
                files[p] = "U"
            return {
                "is_repo": data.get("is_repo", True),
                "available": True,
                "files": files,
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Sandbox git status failed: {exc}")

    @router.get("/git/diff")
    @require_permission("git:read")
    async def git_diff(request: Request, path: str):
        try:
            token = _issue_token(request, {"git:diff"})
            data = await client.git_diff("working", capability_token=token)
            full_diff = data.get("diff", "") or ""
            marker = f"diff --git a/{path} b/{path}"
            if marker not in full_diff:
                return {"diff": "", "path": path}

            chunks = full_diff.split("diff --git ")
            matched = ""
            for chunk in chunks:
                if chunk.startswith(f"a/{path} b/{path}"):
                    matched = "diff --git " + chunk
                    break
            return {"diff": matched, "path": path}
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Sandbox git diff failed: {exc}")

    @router.get("/git/show")
    @require_permission("git:read")
    async def git_show(request: Request, path: str):
        # Fallback behavior: returns current file contents in hosted compat mode.
        try:
            token = _issue_token(request, {"files:read"})
            data = await client.read_file(path, capability_token=token)
            return {"content": data.get("content", ""), "path": path, "is_new": False}
        except Exception:
            return {"content": None, "path": path, "error": "Not in HEAD", "is_new": True}

    return router
