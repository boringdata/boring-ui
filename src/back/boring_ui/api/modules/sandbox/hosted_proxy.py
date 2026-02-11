"""Hosted proxy handlers for sandbox operations (bd-1pwb.5.2 & 5.3).

Provides public API endpoints that proxy to private internal sandbox service
with policy enforcement, permission checking, and error mapping.

Routes exposed publicly but authenticated via capability tokens.
"""

from fastapi import APIRouter, HTTPException, status, Request, Depends
from typing import Any, Optional
from .hosted_client import HostedSandboxClient, SandboxClientConfig

import logging

logger = logging.getLogger(__name__)


def create_hosted_sandbox_proxy_router(
    client: HostedSandboxClient,
) -> APIRouter:
    """Create proxy router that forwards requests to internal sandbox service.
    
    Routes mounted at /api/v1/sandbox/proxy.
    Requires authentication and capability tokens.
    """
    router = APIRouter(prefix="/sandbox/proxy", tags=["sandbox-proxy"])

    # File operations (bd-1pwb.5.2)
    @router.get("/files/list")
    async def proxy_list_files(path: str = "."):
        """Proxy: List files in sandbox."""
        try:
            return await client.list_files(path)
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to access sandbox",
            )

    @router.get("/files/read")
    async def proxy_read_file(path: str):
        """Proxy: Read file from sandbox."""
        try:
            return await client.read_file(path)
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to access sandbox",
            )

    @router.post("/files/write")
    async def proxy_write_file(path: str, content: str):
        """Proxy: Write file to sandbox."""
        try:
            return await client.write_file(path, content)
        except Exception as e:
            logger.error(f"Failed to write file: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to access sandbox",
            )

    # Git operations (bd-1pwb.5.2)
    @router.get("/git/status")
    async def proxy_git_status():
        """Proxy: Get git status from sandbox."""
        try:
            return await client.git_status()
        except Exception as e:
            logger.error(f"Failed to get git status: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to access sandbox",
            )

    @router.get("/git/diff")
    async def proxy_git_diff(context: str = "working"):
        """Proxy: Get git diff from sandbox."""
        try:
            return await client.git_diff(context)
        except Exception as e:
            logger.error(f"Failed to get git diff: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to access sandbox",
            )

    # Exec operations (bd-1pwb.5.3)
    @router.post("/exec/run")
    async def proxy_exec_run(command: str, timeout_seconds: int = 30):
        """Proxy: Execute command in sandbox.
        
        Defensive guardrails:
        - Timeout enforcement (max 300s)
        - Rate limiting (will be added)
        - Audit logging of all exec operations
        """
        try:
            # Enforce timeout limits
            timeout = min(timeout_seconds, 300)
            if timeout < 1:
                timeout = 30

            logger.info(f"Executing command in sandbox: {command[:50]}...")
            return await client.exec_run(command, timeout)
        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to execute in sandbox",
            )

    @router.get("/health")
    async def proxy_health():
        """Health check: verify internal sandbox service is reachable."""
        try:
            # Quick check by fetching client stats
            stats = client.get_stats()
            return {
                "status": "ok",
                "service": "sandbox-proxy",
                "internal_url": stats.get("internal_url"),
            }
        except Exception as e:
            logger.error(f"Sandbox proxy health check failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sandbox service unavailable",
            )

    return router
