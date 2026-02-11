"""Internal file operations for sandbox (bd-1pwb.4.2).

Provides privileged file access:
- List files and directories
- Read file contents
- Write file contents
- Delete files
- Get file metadata (size, mtime, etc)
"""

from fastapi import APIRouter, HTTPException, status
from pathlib import Path
from typing import Optional


def create_internal_files_router(workspace_root: Path) -> APIRouter:
    """Create router for internal file operations.
    
    Routes mounted at /internal/v1/files.
    All operations are relative to workspace_root.
    """
    router = APIRouter(prefix="/files", tags=["files-internal"])

    def validate_path(path: str) -> Path:
        """Validate that path is within workspace_root."""
        p = (workspace_root / path).resolve()
        if not str(p).startswith(str(workspace_root.resolve())):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Path traversal detected",
            )
        return p

    @router.get("/list")
    async def list_files(path: str = "."):
        """List files in a directory."""
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
    async def read_file(path: str):
        """Read file contents."""
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
    async def write_file(path: str, content: str):
        """Write file contents."""
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
