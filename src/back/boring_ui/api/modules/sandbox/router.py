"""API router for sandbox operations.

Provides:
- Status endpoint for sandbox state
- Log endpoints (fetch and stream)
- Proxy for all sandbox-agent API calls
"""
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
import httpx

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

    # Proxy endpoints for sandbox-agent API
    @router.api_route(
        "/sandbox/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    )
    async def proxy_to_sandbox(request: Request, path: str):
        """Proxy requests to sandbox-agent.

        Forwards all requests under /api/sandbox/* to the running
        sandbox-agent, preserving method, headers, and body.
        """
        # Skip our own endpoints
        if path in ("status", "start", "stop", "health", "logs", "logs/stream"):
            raise HTTPException(
                status_code=404,
                detail=f"Use /api/sandbox/{path} directly",
            )

        try:
            base_url = await manager.get_base_url()
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Sandbox not available: {e}",
            )

        # Build target URL
        target_url = f"{base_url}/{path}"
        if request.url.query:
            target_url = f"{target_url}?{request.url.query}"

        # Forward request
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Filter headers (remove hop-by-hop headers)
                forward_headers = {
                    k: v
                    for k, v in request.headers.items()
                    if k.lower()
                    not in (
                        "host",
                        "connection",
                        "keep-alive",
                        "transfer-encoding",
                        "te",
                        "trailer",
                        "upgrade",
                    )
                }

                # Inject service token for sandbox-agent auth
                if manager.service_token:
                    forward_headers["authorization"] = (
                        f"Bearer {manager.service_token}"
                    )

                body = await request.body()
                resp = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=forward_headers,
                    content=body,
                )

                # Check if this is a streaming response
                content_type = resp.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    # Stream SSE responses
                    async def stream_response():
                        async with httpx.AsyncClient(timeout=None) as stream_client:
                            async with stream_client.stream(
                                method=request.method,
                                url=target_url,
                                headers=forward_headers,
                                content=body,
                            ) as stream_resp:
                                async for chunk in stream_resp.aiter_bytes():
                                    yield chunk

                    return StreamingResponse(
                        stream_response(),
                        status_code=resp.status_code,
                        media_type=content_type,
                    )

                # Filter response headers
                response_headers = {
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower()
                    not in (
                        "content-encoding",
                        "content-length",
                        "transfer-encoding",
                        "connection",
                    )
                }

                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    headers=response_headers,
                    media_type=resp.headers.get("content-type"),
                )

            except httpx.ConnectError:
                raise HTTPException(
                    status_code=503,
                    detail="Cannot connect to sandbox-agent",
                )
            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=504,
                    detail="Sandbox-agent request timed out",
                )

    return router
