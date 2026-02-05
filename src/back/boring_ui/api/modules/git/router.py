"""Git operation routes for boring-ui API."""
from fastapi import APIRouter

from ...config import APIConfig
from .service import GitService


def create_git_router(config: APIConfig) -> APIRouter:
    """Create git operations router.
    
    Args:
        config: API configuration with workspace_root
        
    Returns:
        FastAPI router with git endpoints
    """
    router = APIRouter(tags=['git'])
    service = GitService(config)
    
    @router.get('/status')
    async def get_status():
        """Get git repository status.
        
        Returns:
            dict with is_repo (bool) and files (dict of status entries)
        """
        return service.get_status()
    
    @router.get('/diff')
    async def get_diff(path: str):
        """Get diff for a specific file against HEAD.
        
        Args:
            path: File path relative to workspace root
            
        Returns:
            dict with diff content and path
        """
        return service.get_diff(path)
    
    @router.get('/show')
    async def get_show(path: str):
        """Get file contents at HEAD.
        
        Args:
            path: File path relative to workspace root
            
        Returns:
            dict with content at HEAD (or null if not tracked)
        """
        return service.get_show(path)
    
    return router
