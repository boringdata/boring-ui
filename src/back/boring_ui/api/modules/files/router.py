"""File operation routes for boring-ui API."""
from fastapi import APIRouter, Query, Request

from ...config import APIConfig
from ...policy import enforce_delegated_policy_or_none
from ...storage import Storage
from .schemas import FileContent, RenameRequest, MoveRequest
from .service import FileService


def create_file_router(config: APIConfig, storage: Storage) -> APIRouter:
    """Create file operations router.
    
    Args:
        config: API configuration (for path validation)
        storage: Storage backend
        
    Returns:
        Configured APIRouter with file endpoints
    """
    router = APIRouter(tags=['files'])
    service = FileService(config, storage)
    
    @router.get('/list')
    async def list_files(request: Request, path: str = '.'):
        """List directory contents."""
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.read"},
            operation="workspace-core.files.list",
        )
        if deny is not None:
            return deny
        return service.list_directory(path)
    
    @router.get('/read')
    async def read_file(request: Request, path: str):
        """Read file contents."""
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.read"},
            operation="workspace-core.files.read",
        )
        if deny is not None:
            return deny
        return service.read_file(path)
    
    @router.put('/write')
    async def write_file(request: Request, path: str, body: FileContent):
        """Write file contents."""
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.write"},
            operation="workspace-core.files.write",
        )
        if deny is not None:
            return deny
        return service.write_file(path, body.content)
    
    @router.delete('/delete')
    async def delete_file(request: Request, path: str):
        """Delete file."""
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.write"},
            operation="workspace-core.files.delete",
        )
        if deny is not None:
            return deny
        return service.delete_file(path)
    
    @router.post('/rename')
    async def rename_file(request: Request, body: RenameRequest):
        """Rename file.
        
        Args:
            body: Request with old_path and new_path
            
        Returns:
            dict with success status and new path
        """
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.write"},
            operation="workspace-core.files.rename",
        )
        if deny is not None:
            return deny
        return service.rename_file(body.old_path, body.new_path)
    
    @router.post('/move')
    async def move_file(request: Request, body: MoveRequest):
        """Move file to a different directory.
        
        Args:
            body: Request with src_path and dest_dir
            
        Returns:
            dict with success status and new path
        """
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.write"},
            operation="workspace-core.files.move",
        )
        if deny is not None:
            return deny
        return service.move_file(body.src_path, body.dest_dir)
    
    @router.get('/search')
    async def search_files(
        request: Request,
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
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.read"},
            operation="workspace-core.files.search",
        )
        if deny is not None:
            return deny
        return service.search_files(q, path)
    
    return router
