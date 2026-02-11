"""Local API router composition (bd-1adh.2.1).

Composes workspace-scoped routers (files, git, exec) into a single /internal/v1 endpoint.
"""

from fastapi import APIRouter
from pathlib import Path
from .files import create_files_router
from .git import create_git_router
from .exec import create_exec_router


def create_local_api_router(workspace_root: Path) -> APIRouter:
    """Create the main local API router.

    Composes all workspace-scoped operation routers under /internal/v1:
    - /internal/v1/files/* (file operations)
    - /internal/v1/git/* (git operations)
    - /internal/v1/exec/* (command execution)

    Args:
        workspace_root: Root path for all workspace operations

    Returns:
        FastAPI APIRouter for mounting at app root
    """
    # Create main v1 router
    v1_router = APIRouter(prefix="/internal/v1", tags=["local-api-v1"])

    # Compose sub-routers
    v1_router.include_router(create_files_router(workspace_root))
    v1_router.include_router(create_git_router(workspace_root))
    v1_router.include_router(create_exec_router(workspace_root))

    return v1_router
