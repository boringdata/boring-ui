"""API router for sandbox lifecycle operations.

Provides:
- Status endpoint for sandbox state
- Start/stop/health endpoints
- Log endpoints (fetch and stream)

Service API calls (agents, sessions, messages) go directly from the
browser to sandbox-agent via Direct Connect (token auth + CORS).
"""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .manager import SandboxManager


def create_sandbox_router(manager: SandboxManager) -> APIRouter:
    """Create the sandbox API router.

    Args:
        manager: SandboxManager instance for sandbox operations

    Returns:
        Configured APIRouter
    """
    router = APIRouter(tags=["sandbox"])

    @router.get("/sandbox/status")
    async def get_status():
        """Get sandbox status.

        Returns sandbox info if running, or status indicator if not.
        """
        info = await manager.get_info()
        if info:
            return {
                "id": info.id,
                "status": info.status,
                "base_url": info.base_url,
                "workspace_path": info.workspace_path,
                "provider": info.provider,
            }
        return {"status": "not_running"}

    @router.post("/sandbox/start")
    async def start_sandbox():
        """Start the sandbox if not already running."""
        try:
            info = await manager.ensure_running()
            return {
                "id": info.id,
                "status": info.status,
                "base_url": info.base_url,
                "workspace_path": info.workspace_path,
                "provider": info.provider,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/sandbox/stop")
    async def stop_sandbox():
        """Stop the sandbox."""
        await manager.shutdown()
        return {"status": "stopped"}

    @router.get("/sandbox/health")
    async def health_check():
        """Check sandbox health."""
        healthy = await manager.health_check()
        return {"healthy": healthy}

    @router.get("/sandbox/logs")
    async def get_logs(limit: int = 100):
        """Get sandbox-agent logs.

        Args:
            limit: Maximum number of log lines to return
        """
        logs = await manager.get_logs(limit)
        return {"logs": logs}

    @router.get("/sandbox/logs/stream")
    async def stream_logs():
        """SSE stream of sandbox-agent logs."""

        async def generate():
            async for line in manager.stream_logs():
                yield f"data: {json.dumps({'log': line})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return router
