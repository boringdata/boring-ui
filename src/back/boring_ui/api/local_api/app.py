"""Local API application factory (bd-1adh.2.1).

Creates a standalone local_api FastAPI app for workspace-scoped operations.
Includes health checks and internal endpoints.

In LOCAL mode: can be mounted in-process to the control plane
In HOSTED mode: runs as a separate service in the private network/sprite
"""

from fastapi import FastAPI
from pathlib import Path
from .router import create_local_api_router


def create_local_api_app(workspace_root: Path) -> FastAPI:
    """Create a standalone local_api FastAPI application.

    The local_api app provides workspace-scoped operations on a private plane:
    - No end-user authentication (trust boundary is deployment topology)
    - Capability token auth validates callers (control plane only in hosted mode)
    - Health checks for readiness/liveness probes

    Args:
        workspace_root: Root path for all workspace operations

    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="boring-ui Local API",
        description="Workspace-scoped file, git, and exec operations (private plane)",
        version="1.0.0",
    )

    # Mount main router at /internal
    router = create_local_api_router(workspace_root)
    app.include_router(router)

    # Health check endpoint
    @app.get("/health")
    async def health():
        """Basic health check for readiness/liveness probes."""
        return {
            "status": "ok",
            "service": "local-api",
            "workspace_root": str(workspace_root),
        }

    # Info endpoint
    @app.get("/internal/info")
    async def info():
        """Info about the local_api service."""
        return {
            "service": "local-api",
            "version": "1.0.0",
            "workspace_root": str(workspace_root),
            "endpoints": {
                "health": "/health",
                "files": "/internal/v1/files/*",
                "git": "/internal/v1/git/*",
                "exec": "/internal/v1/exec/*",
            },
        }

    return app
