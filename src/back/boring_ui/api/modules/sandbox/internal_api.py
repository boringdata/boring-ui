"""Private internal API service for sandbox operations (bd-1pwb.4.1).

Provides internal-only endpoints for:
- File operations (read, write, list)
- Git operations (status, diff, commit)
- Exec operations (run commands with resource limits)

This service is NOT advertised in /api/capabilities and only accessible
from control plane (direct connection via capability tokens).
"""

from fastapi import APIRouter, HTTPException, status

def create_internal_sandbox_router() -> APIRouter:
    """Create router for private sandbox internal operations.
    
    Routes mounted at /internal/v1 prefix.
    Requires capability token authorization.
    """
    router = APIRouter(prefix="/sandbox", tags=["sandbox-internal"])

    @router.get("/health")
    async def health_check():
        """Health check endpoint for internal service."""
        return {
            "status": "ok",
            "service": "sandbox-internal",
            "version": "1.0",
        }

    @router.get("/info")
    async def service_info():
        """Get internal service metadata."""
        return {
            "name": "sandbox-internal",
            "version": "1.0",
            "endpoints": {
                "files": "/files",
                "git": "/git",
                "exec": "/exec",
            },
        }

    return router
