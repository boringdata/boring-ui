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
from ..contracts import WriteFileRequest


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
    async def write_file(request: Request, body: WriteFileRequest):
        """Write file contents.

        Requires capability: files:write
        """
        try:
            p = validate_path(body.path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body.content)
            return {
                "path": body.path,
                "size": len(body.content),
                "written": True,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @router.delete("/delete")
    @require_capability("files:write")
    async def delete_file(request: Request, path: str):
        """Delete file or directory.

        Requires capability: files:write
        """
        try:
            p = validate_path(path)
            if not p.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not found",
                )
            if p.is_dir():
                import shutil
                shutil.rmtree(p)
            else:
                p.unlink()
            return {"path": path, "deleted": True}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @router.post("/rename")
    @require_capability("files:write")
    async def rename_file(request: Request, old_path: str, new_path: str):
        """Rename file or directory.

        Requires capability: files:write
        """
        try:
            old_p = validate_path(old_path)
            new_p = validate_path(new_path)
            if not old_p.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not found",
                )
            if new_p.exists():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Target exists",
                )
            new_p.parent.mkdir(parents=True, exist_ok=True)
            old_p.rename(new_p)
            return {"old_path": old_path, "new_path": new_path, "renamed": True}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @router.post("/move")
    @require_capability("files:write")
    async def move_file(request: Request, src_path: str, dest_dir: str):
        """Move file or directory into a destination directory.

        Requires capability: files:write
        """
        try:
            src_p = validate_path(src_path)
            dest_d = validate_path(dest_dir)
            if not src_p.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Not found",
                )
            if not dest_d.is_dir():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Destination is not a directory",
                )
            dest_p = dest_d / src_p.name
            if dest_p.exists():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Target exists",
                )
            import shutil
            shutil.move(str(src_p), str(dest_p))
            rel_dest = str(dest_p.relative_to(workspace_root.resolve()))
            return {"src_path": src_path, "dest_path": rel_dest, "moved": True}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    return router
