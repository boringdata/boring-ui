"""Local API file operations (bd-1adh.2.1).

Provides workspace-scoped file access:
- List files and directories
- Read file contents
- Write file contents
- Delete files
- Get file metadata (size, mtime, etc)

All routes require capability token authorization via bd-1pwb.3.2.
Workspace isolation is enforced via path validation.
"""

from fastapi import APIRouter, HTTPException, status, Request
from pathlib import Path
from typing import Optional
from ..sandbox_auth import require_capability


def create_files_router(workspace_root: Path) -> APIRouter:
    """Create router for file operations.

    Routes mounted at /internal/v1/files.
    All operations are relative to workspace_root.
    Requires capability token authorization.

    Args:
        workspace_root: Root path for all file operations

    Returns:
        FastAPI APIRouter for mounting
    """
    router = APIRouter(prefix="/files", tags=["files-internal"])

    def validate_path(path: str) -> Path:
        """Validate that path is within workspace_root.

        Args:
            path: Path to validate (relative or absolute)

        Returns:
            Resolved absolute path within workspace_root

        Raises:
            HTTPException: 403 if path traversal detected
        """
        p = (workspace_root / path).resolve()
        ws_root = workspace_root.resolve()
        try:
            # Proper ancestry check: throws ValueError if p is not relative to ws_root
            p.relative_to(ws_root)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Path traversal detected",
            )
        return p

    @router.get("/list")
    @require_capability("files:list")
    async def list_files(request: Request, path: str = "."):
        """List files in a directory.

        Requires capability: files:list
        """
        try:
            p = validate_path(path)
            if not p.is_dir():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not a directory",
                )

            items = []
            for item in sorted(p.iterdir()):
                items.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                })
            return {"files": items}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @router.get("/read")
    @require_capability("files:read")
    async def read_file(request: Request, path: str):
        """Read file contents.

        Requires capability: files:read
        """
        try:
            p = validate_path(path)
            if not p.is_file():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not a file",
                )

            content = p.read_text()
            return {
                "path": path,
                "content": content,
                "size": len(content),
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @router.post("/write")
    @require_capability("files:write")
    async def write_file(request: Request, path: str, content: str):
        """Write file contents.

        Requires capability: files:write
        """
        try:
            p = validate_path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return {
                "path": path,
                "size": len(content),
                "written": True,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    return router
