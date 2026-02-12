"""API router for Companion server lifecycle management.

Provides status, start/stop, health, and log endpoints.
No request proxy — Companion uses Direct Connect (browser -> server).
"""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .manager import CompanionManager


def create_companion_router(manager: CompanionManager) -> APIRouter:
    """Create the Companion lifecycle API router."""
    router = APIRouter(tags=["companion"])

    @router.get("/companion/status")
    async def get_status():
        """Get Companion server status."""
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

    @router.post("/companion/start")
    async def start_companion():
        """Start the Companion server if not already running."""
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

    @router.post("/companion/stop")
    async def stop_companion():
        """Stop the Companion server."""
        await manager.shutdown()
        return {"status": "stopped"}

    @router.get("/companion/health")
    async def health_check():
        """Check Companion server health."""
        healthy = await manager.health_check()
        return {"healthy": healthy}

    @router.get("/companion/logs")
    async def get_logs(limit: int = 100):
        """Get Companion server logs."""
        logs = await manager.get_logs(limit)
        return {"logs": logs}

    @router.get("/companion/logs/stream")
    async def stream_logs():
        """SSE stream of Companion server logs."""

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
