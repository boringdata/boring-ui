"""Internal git operations for sandbox (bd-1pwb.4.2).

Provides privileged git access:
- Status (staged, unstaged, untracked)
- Diff (working tree vs staged vs HEAD)
- Log (commit history)
- Commit (with message)
- Branch management
"""

from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import Optional


def create_internal_git_router(workspace_root: Path) -> APIRouter:
    """Create router for internal git operations.
    
    Routes mounted at /internal/v1/git.
    All operations use workspace_root as repo root.
    """
    router = APIRouter(prefix="/git", tags=["git-internal"])

    @router.get("/status")
    async def git_status():
        """Get git status (files, staged, unstaged, untracked)."""
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
    async def git_diff(context: str = "working"):
        """Get git diff.
        
        context: 'working' (vs staged), 'staged' (vs HEAD), 'head' (last commit)
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
    async def git_log(limit: int = 10):
        """Get commit history."""
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
