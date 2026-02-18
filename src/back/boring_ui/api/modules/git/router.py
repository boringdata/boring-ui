"""Git operation routes for boring-ui API."""
from fastapi import APIRouter, Request

from ...config import APIConfig
from ...policy import enforce_delegated_policy_or_none
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
    async def get_status(request: Request):
        """Get git repository status.
        
        Returns:
            dict with is_repo (bool) and files (dict of status entries)
        """
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.git.read"},
            operation="workspace-core.git.status",
        )
        if deny is not None:
            return deny
        return service.get_status()
    
    @router.get('/diff')
    async def get_diff(request: Request, path: str):
        """Get diff for a specific file against HEAD.
        
        Args:
            path: File path relative to workspace root
            
        Returns:
            dict with diff content and path
        """
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.git.read"},
            operation="workspace-core.git.diff",
        )
        if deny is not None:
            return deny
        return service.get_diff(path)
    
    @router.get('/show')
    async def get_show(request: Request, path: str):
        """Get file contents at HEAD.
        
        Args:
            path: File path relative to workspace root
            
        Returns:
            dict with content at HEAD (or null if not tracked)
        """
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.git.read"},
            operation="workspace-core.git.show",
        )
        if deny is not None:
            return deny
        return service.get_show(path)
    
    return router
