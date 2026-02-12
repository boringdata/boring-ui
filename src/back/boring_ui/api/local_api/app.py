"""Local API application factory (bd-1adh.2.1).

Creates a standalone local_api FastAPI app for workspace-scoped operations.
Includes health checks and internal endpoints.

In LOCAL mode: can be mounted in-process to the control plane
In HOSTED mode: runs as a separate service in the private network/sprite
"""

from fastapi import FastAPI
from pathlib import Path
from typing import Optional
from .router import create_local_api_router
from ..sandbox_auth import add_capability_auth_middleware
from ..capability_tokens import CapabilityTokenValidator


def create_local_api_app(
    workspace_root: Path,
    capability_public_key_pem: Optional[str] = None,
) -> FastAPI:
    """Create a standalone local_api FastAPI application.

    The local_api app provides workspace-scoped operations on a private plane:
    - No end-user authentication (trust boundary is deployment topology)
    - Capability token auth validates callers (control plane only in hosted mode)
    - Health checks for readiness/liveness probes

    Args:
        workspace_root: Root path for all workspace operations
        capability_public_key_pem: RSA public key PEM for capability token
            validation.  When provided, all /internal/v1 routes require a
            valid capability token.  When None (e.g. LOCAL in-process mount),
            the middleware is skipped.

    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="boring-ui Local API",
        description="Workspace-scoped file, git, and exec operations (private plane)",
        version="1.0.0",
    )

    # Capability token auth — validates callers when running as separate service
    validator = (
        CapabilityTokenValidator(capability_public_key_pem)
        if capability_public_key_pem
        else None
    )
    add_capability_auth_middleware(app, validator)

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
