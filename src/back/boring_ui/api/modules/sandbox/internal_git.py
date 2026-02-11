"""Internal git operations for sandbox (bd-1pwb.4.2).

Provides privileged git access:
- Status (staged, unstaged, untracked)
- Diff (working tree vs staged vs HEAD)
- Log (commit history)
- Commit (with message)
- Branch management

All routes require capability token authorization via bd-1pwb.3.2.
"""

from fastapi import APIRouter, HTTPException, status, Request
from pathlib import Path
from typing import Optional
from ...sandbox_auth import require_capability


def create_internal_git_router(workspace_root: Path) -> APIRouter:
    """Create router for internal git operations.

    Routes mounted at /internal/v1/git.
    All operations use workspace_root as repo root.
    Requires capability token authorization.
    """
    router = APIRouter(prefix="/git", tags=["git-internal"])

    @router.get("/status")
    @require_capability("git:status")
    async def git_status(request: Request):
        """Get git status (files, staged, unstaged, untracked).

        Requires capability: git:status
        """
        try:
            # Placeholder: would use GitPython or subprocess
            return {
                "branch": "main",
                "staged": [],
                "unstaged": [],
                "untracked": [],
                "clean": True,
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @router.get("/diff")
    @require_capability("git:diff")
    async def git_diff(request: Request, context: str = "working"):
        """Get git diff.

        context: 'working' (vs staged), 'staged' (vs HEAD), 'head' (last commit)
        Requires capability: git:diff
        """
        try:
            # Placeholder: would use GitPython or subprocess
            return {
                "context": context,
                "diff": "",
                "stats": {
                    "insertions": 0,
                    "deletions": 0,
                    "files_changed": 0,
                },
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @router.get("/log")
    @require_capability("git:log")
    async def git_log(request: Request, limit: int = 10):
        """Get commit history.

        Requires capability: git:log
        """
        try:
            # Placeholder: would use GitPython or subprocess
            return {
                "commits": [],
                "total": 0,
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    return router
