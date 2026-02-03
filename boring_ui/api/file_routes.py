"""File operation routes for boring-ui API."""
import fnmatch
from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel
from .config import APIConfig
from .storage import Storage


class FileContent(BaseModel):
    """Request body for file content."""
    content: str


class RenameRequest(BaseModel):
    """Request body for file rename."""
    old_path: str
    new_path: str


class MoveRequest(BaseModel):
    """Request body for file move."""
    src_path: str
    dest_dir: str


def create_file_router(config: APIConfig, storage: Storage) -> APIRouter:
    """Create file operations router.

    Args:
        config: API configuration (for path validation)
        storage: Storage backend

    Returns:
        Configured APIRouter with file endpoints
    """
    router = APIRouter(tags=['files'])

    def validate_and_relativize(path: str | Path) -> Path:
        """Validate path and return relative path.

        Args:
            path: Path to validate

        Returns:
            Path relative to workspace root

        Raises:
            HTTPException: If path is invalid or outside workspace
        """
        try:
            validated = config.validate_path(Path(path))
            return validated.relative_to(config.workspace_root)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get('/tree')
    async def get_tree(path: str = '.'):
        """List directory contents.

        Args:
            path: Directory path relative to workspace root

        Returns:
            dict with entries list and path
        """
        rel_path = validate_and_relativize(path)
        entries = storage.list_dir(rel_path)
        return {'entries': entries, 'path': path}

    @router.get('/file')
    async def get_file(path: str):
        """Read file contents.

        Args:
            path: File path relative to workspace root

        Returns:
            dict with content string and path
        """
        rel_path = validate_and_relativize(path)
        try:
            content = storage.read_file(rel_path)
            return {'content': content, 'path': path}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f'File not found: {path}')
        except IsADirectoryError:
            raise HTTPException(status_code=400, detail=f'Path is a directory: {path}')

    @router.put('/file')
    async def put_file(path: str, body: FileContent):
        """Write file contents.

        Args:
            path: File path relative to workspace root
            body: Request body with content string

        Returns:
            dict with success status and path
        """
        rel_path = validate_and_relativize(path)
        try:
            storage.write_file(rel_path, body.content)
            return {'success': True, 'path': path}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f'Write failed: {str(e)}')

    @router.delete('/file')
    async def delete_file(path: str):
        """Delete file.

        Args:
            path: File path relative to workspace root

        Returns:
            dict with success status
        """
        rel_path = validate_and_relativize(path)
        try:
            storage.delete(rel_path)
            return {'success': True, 'path': path}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f'File not found: {path}')

    @router.post('/file/rename')
    async def rename_file(body: RenameRequest):
        """Rename file.

        Args:
            body: Request with old_path and new_path

        Returns:
            dict with success status and new path
        """
        old_rel = validate_and_relativize(body.old_path)
        new_rel = validate_and_relativize(body.new_path)
        try:
            storage.rename(old_rel, new_rel)
            return {'success': True, 'old_path': body.old_path, 'new_path': body.new_path}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f'File not found: {body.old_path}')
        except FileExistsError:
            raise HTTPException(status_code=409, detail=f'Target exists: {body.new_path}')

    @router.post('/file/move')
    async def move_file(body: MoveRequest):
        """Move file to a different directory.

        Args:
            body: Request with src_path and dest_dir

        Returns:
            dict with success status and new path
        """
        src_rel = validate_and_relativize(body.src_path)
        dest_rel = validate_and_relativize(body.dest_dir)
        try:
            new_path = storage.move(src_rel, dest_rel)
            return {'success': True, 'old_path': body.src_path, 'new_path': str(new_path)}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f'File not found: {body.src_path}')
        except NotADirectoryError:
            raise HTTPException(status_code=400, detail=f'Destination is not a directory: {body.dest_dir}')

    @router.get('/search')
    async def search_files(
        q: str = Query(..., min_length=1, description='Search pattern (glob-style)'),
        path: str = Query('.', description='Directory to search in'),
    ):
        """Search files by name pattern.

        Uses glob-style pattern matching (e.g., *.py, test_*).

        Args:
            q: Search pattern
            path: Directory to search in

        Returns:
            dict with matches list
        """
        rel_path = validate_and_relativize(path)
        matches: list[dict[str, Any]] = []

        def search_recursive(dir_path: Path, depth: int = 0):
            """Recursively search directory."""
            if depth > 10:  # Prevent infinite recursion
                return

            try:
                entries = storage.list_dir(dir_path)
                for entry in entries:
                    entry_path = Path(entry['path'])
                    name = entry_path.name

                    # Match against pattern
                    if fnmatch.fnmatch(name.lower(), q.lower()):
                        matches.append(entry)

                    # Recurse into directories
                    if entry['is_dir']:
                        search_recursive(entry_path, depth + 1)
            except (FileNotFoundError, PermissionError):
                pass

        search_recursive(rel_path)
        return {'matches': matches, 'pattern': q, 'path': path}

    return router
