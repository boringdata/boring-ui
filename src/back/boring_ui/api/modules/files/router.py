"""File operation routes for boring-ui API."""
from fastapi import APIRouter, Query

from ...config import APIConfig
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
    async def list_files(path: str = '.'):
        """List directory contents."""
        return service.list_directory(path)
    
    @router.get('/read')
    async def read_file(path: str):
        """Read file contents."""
        return service.read_file(path)
    
    @router.put('/write')
    async def write_file(path: str, body: FileContent):
        """Write file contents."""
        return service.write_file(path, body.content)
    
    @router.delete('/delete')
    async def delete_file(path: str):
        """Delete file."""
        return service.delete_file(path)
    
    @router.post('/rename')
    async def rename_file(body: RenameRequest):
        """Rename file.
        
        Args:
            body: Request with old_path and new_path
            
        Returns:
            dict with success status and new path
        """
        return service.rename_file(body.old_path, body.new_path)
    
    @router.post('/move')
    async def move_file(body: MoveRequest):
        """Move file to a different directory.
        
        Args:
            body: Request with src_path and dest_dir
            
        Returns:
            dict with success status and new path
        """
        return service.move_file(body.src_path, body.dest_dir)
    
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
        return service.search_files(q, path)
    
    return router
