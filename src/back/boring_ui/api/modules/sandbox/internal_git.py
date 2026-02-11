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
import subprocess
from ...sandbox_auth import require_capability


def create_internal_git_router(workspace_root: Path) -> APIRouter:
    """Create router for internal git operations.

    Routes mounted at /internal/v1/git.
    All operations use workspace_root as repo root.
    Requires capability token authorization.
    """
    router = APIRouter(prefix="/git", tags=["git-internal"])

    def run_git(args: list[str]) -> str:
        result = subprocess.run(
            ["git"] + args,
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Git error: {result.stderr.strip()}",
            )
        return result.stdout

    def is_repo() -> bool:
        try:
            run_git(["rev-parse", "--git-dir"])
            return True
        except HTTPException:
            return False

    @router.get("/status")
    @require_capability("git:status")
    async def git_status(request: Request):
        """Get git status (files, staged, unstaged, untracked).

        Requires capability: git:status
        """
        try:
            if not is_repo():
                return {
                    "branch": "",
                    "staged": [],
                    "unstaged": [],
                    "untracked": [],
                    "clean": True,
                    "is_repo": False,
                }

            branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
            porcelain = run_git(["status", "--porcelain"])
            staged: list[str] = []
            unstaged: list[str] = []
            untracked: list[str] = []

            for line in porcelain.splitlines():
                if len(line) < 3:
                    continue
                x, y = line[0], line[1]
                file_path = line[3:]
                if x == "?" and y == "?":
                    untracked.append(file_path)
                    continue
                if x != " ":
                    staged.append(file_path)
                if y != " ":
                    unstaged.append(file_path)

            return {
                "branch": branch,
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "clean": len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0,
                "is_repo": True,
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
            if not is_repo():
                return {
                    "context": context,
                    "diff": "",
                    "stats": {"insertions": 0, "deletions": 0, "files_changed": 0},
                    "is_repo": False,
                }

            if context == "staged":
                diff = run_git(["diff", "--cached"])
                stat_text = run_git(["diff", "--cached", "--numstat"])
            elif context == "head":
                diff = run_git(["show", "--format=", "HEAD"])
                stat_text = run_git(["show", "--format=", "--numstat", "HEAD"])
            else:
                diff = run_git(["diff"])
                stat_text = run_git(["diff", "--numstat"])

            insertions = 0
            deletions = 0
            files_changed = 0
            for line in stat_text.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    files_changed += 1
                    try:
                        insertions += int(parts[0]) if parts[0].isdigit() else 0
                        deletions += int(parts[1]) if parts[1].isdigit() else 0
                    except ValueError:
                        pass

            return {
                "context": context,
                "diff": diff,
                "stats": {
                    "insertions": insertions,
                    "deletions": deletions,
                    "files_changed": files_changed,
                },
                "is_repo": True,
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
            if not is_repo():
                return {"commits": [], "total": 0, "is_repo": False}

            safe_limit = max(1, min(limit, 200))
            log_output = run_git(
                [
                    "log",
                    f"-n{safe_limit}",
                    "--date=iso",
                    "--pretty=format:%H%x1f%an%x1f%ad%x1f%s",
                ]
            )
            commits = []
            for line in log_output.splitlines():
                parts = line.split("\x1f")
                if len(parts) == 4:
                    commits.append(
                        {
                            "sha": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "subject": parts[3],
                        }
                    )
            return {
                "commits": commits,
                "total": len(commits),
                "is_repo": True,
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    return router
