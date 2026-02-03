"""File operation routes."""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .config import APIConfig
from .storage import Storage


class FileContent(BaseModel):
    """Request body for file write operations."""
    content: str


class RenameRequest(BaseModel):
    """Request body for file rename operation."""
    old_path: str
    new_path: str


class MoveRequest(BaseModel):
    """Request body for file move operation."""
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

    @router.get('/tree')
    async def get_tree(path: str = '.'):
        """List directory contents."""
        try:
            validated = config.validate_path(path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        try:
            rel_path = validated.relative_to(config.workspace_root)
            entries = storage.list_dir(rel_path)
            return {'entries': entries, 'path': path}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f'Directory not found: {path}')

    @router.get('/file')
    async def get_file(path: str = Query(...)):
        """Read file contents."""
        try:
            validated = config.validate_path(path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        try:
            rel_path = validated.relative_to(config.workspace_root)
            content = storage.read_file(rel_path)
            return {'content': content, 'path': path}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f'File not found: {path}')

    @router.put('/file')
    async def put_file(path: str, body: FileContent):
        """Write file contents. Creates parent directories if needed."""
        try:
            validated = config.validate_path(path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        rel_path = validated.relative_to(config.workspace_root)
        storage.write_file(rel_path, body.content)
        return {'success': True, 'path': path}

    @router.delete('/file')
    async def delete_file(path: str = Query(...)):
        """Delete file or directory."""
        try:
            validated = config.validate_path(path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        try:
            rel_path = validated.relative_to(config.workspace_root)
            storage.delete(rel_path)
            return {'success': True, 'path': path}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f'Path not found: {path}')

    @router.post('/file/rename')
    async def rename_file(body: RenameRequest):
        """Rename a file or directory."""
        try:
            old_validated = config.validate_path(body.old_path)
            new_validated = config.validate_path(body.new_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        try:
            old_rel = old_validated.relative_to(config.workspace_root)
            new_rel = new_validated.relative_to(config.workspace_root)
            storage.rename(old_rel, new_rel)
            return {'success': True, 'old_path': body.old_path, 'new_path': body.new_path}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f'Path not found: {body.old_path}')
        except FileExistsError:
            raise HTTPException(status_code=409, detail=f'Path already exists: {body.new_path}')

    @router.post('/file/move')
    async def move_file(body: MoveRequest):
        """Move a file to a different directory."""
        try:
            src_validated = config.validate_path(body.src_path)
            dest_validated = config.validate_path(body.dest_dir)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        try:
            src_rel = src_validated.relative_to(config.workspace_root)
            dest_rel = dest_validated.relative_to(config.workspace_root)
            new_path = storage.move(src_rel, dest_rel)
            return {'success': True, 'src_path': body.src_path, 'new_path': str(new_path)}
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f'Source not found: {body.src_path}')
        except NotADirectoryError:
            raise HTTPException(status_code=400, detail=f'Destination is not a directory: {body.dest_dir}')
        except FileExistsError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @router.get('/search')
    async def search_files(q: str = Query(..., min_length=1), path: str = '.'):
        """Search files by name pattern.

        Uses fnmatch-style patterns (*, ?, [seq]).
        """
        try:
            validated = config.validate_path(path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        matches = []
        root_path = config.workspace_root

        # Walk the directory tree and find matching files
        for dirpath, dirnames, filenames in os.walk(validated):
            # Skip hidden directories
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]

            for filename in filenames:
                if fnmatch.fnmatch(filename.lower(), q.lower()):
                    full_path = Path(dirpath) / filename
                    rel_path = full_path.relative_to(root_path)
                    matches.append({
                        'name': filename,
                        'path': str(rel_path),
                        'is_dir': False,
                    })

            # Also match directory names
            for dirname in dirnames:
                if fnmatch.fnmatch(dirname.lower(), q.lower()):
                    full_path = Path(dirpath) / dirname
                    rel_path = full_path.relative_to(root_path)
                    matches.append({
                        'name': dirname,
                        'path': str(rel_path),
                        'is_dir': True,
                    })

        # Sort by path for consistent output
        matches.sort(key=lambda x: x['path'].lower())

        return {'matches': matches, 'query': q, 'count': len(matches)}

    return router
