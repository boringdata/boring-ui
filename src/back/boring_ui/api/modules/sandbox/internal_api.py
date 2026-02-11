"""Private internal API service for sandbox operations (bd-1pwb.4.1).

Provides internal-only endpoints for:
- File operations (read, write, list)
- Git operations (status, diff, commit)
- Exec operations (run commands with resource limits)

This service is NOT advertised in /api/capabilities and only accessible
from control plane (direct connection via capability tokens).

Routes are composed from individual operation modules:
- internal_files.py: File CRUD operations (bd-1pwb.4.2)
- internal_git.py: Git operations (bd-1pwb.4.2)
- internal_exec.py: Command execution (bd-1pwb.4.3)

All routes require capability token authorization (bd-1pwb.3.2).
"""

from fastapi import APIRouter, Request
from pathlib import Path
from .internal_files import create_internal_files_router
from .internal_git import create_internal_git_router
from .internal_exec import create_internal_exec_router


def create_internal_sandbox_router(workspace_root: Path) -> APIRouter:
    """Create router for private sandbox internal operations.

    Composites all internal operation routers:
    - /internal/v1/files/* - File operations
    - /internal/v1/git/* - Git operations
    - /internal/v1/exec/* - Command execution

    All routes require capability token authorization.

    Args:
        workspace_root: Root directory for all operations

    Returns:
        APIRouter with all internal operation routes
    """
    router = APIRouter(prefix="/internal", tags=["sandbox-internal"])

    @router.get("/health")
    async def health_check():
        """Health check endpoint for internal service.

        Public endpoint (no capability required) for lifespan checks.
        """
        return {
            "status": "ok",
            "service": "sandbox-internal",
            "version": "1.0",
        }

    @router.get("/info")
    async def service_info():
        """Get internal service metadata.

        Public endpoint (no capability required) for service discovery.
        """
        return {
            "name": "sandbox-internal",
            "version": "1.0",
            "endpoints": {
                "files": "/files",
                "git": "/git",
                "exec": "/exec",
            },
        }

    # Compose operation-specific routers
    files_router = create_internal_files_router(workspace_root)
    git_router = create_internal_git_router(workspace_root)
    exec_router = create_internal_exec_router(workspace_root)

    router.include_router(files_router, prefix="/v1")
    router.include_router(git_router, prefix="/v1")
    router.include_router(exec_router, prefix="/v1")

    return router
