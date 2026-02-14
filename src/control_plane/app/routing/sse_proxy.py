"""SSE proxy for streaming events from workspace runtime to browser.

Bead: bd-1joj.19 (STREAM0)

Handles Server-Sent Events streaming for routes like
/w/{workspace_id}/api/v1/agent/sessions/{session_id}/stream.

The SSE proxy:
1. Opens a streaming connection to the workspace runtime
2. Forwards SSE events as they arrive
3. Cleans up upstream on client disconnect
4. Sends a final event on upstream close
5. Enforces an idle timeout (default 5 min)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncGenerator

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .proxy import (
    _build_runtime_url,
    _is_valid_sandbox_name,
    _sanitize_request_headers,
)

logger = logging.getLogger(__name__)

DEFAULT_IDLE_TIMEOUT_SEC = 300  # 5 minutes


async def _stream_sse_events(
    upstream_response: httpx.Response,
    request_id: str | None,
    idle_timeout_sec: float = DEFAULT_IDLE_TIMEOUT_SEC,
) -> AsyncGenerator[bytes, None]:
    """Yield SSE event bytes from an upstream httpx streaming response.

    On idle timeout, yields a timeout event and closes.
    """
    try:
        aiter = upstream_response.aiter_bytes().__aiter__()
        while True:
            try:
                chunk = await asyncio.wait_for(
                    aiter.__anext__(), timeout=idle_timeout_sec,
                )
            except asyncio.TimeoutError:
                logger.info(
                    "SSE idle timeout after %.1fs",
                    idle_timeout_sec,
                    extra={"request_id": request_id},
                )
                yield b"event: timeout\ndata: {\"reason\": \"idle_timeout\"}\n\n"
                return
            except StopAsyncIteration:
                break
            yield chunk

        # Upstream closed normally — send final event.
        yield b"event: close\ndata: {\"reason\": \"upstream_closed\"}\n\n"
    except httpx.ReadError:
        logger.info(
            "SSE upstream read error (client likely disconnected)",
            extra={"request_id": request_id},
        )
    except asyncio.CancelledError:
        logger.info(
            "SSE stream cancelled (client disconnected)",
            extra={"request_id": request_id},
        )
    except Exception as e:
        logger.warning(
            "SSE stream error: %s",
            e,
            extra={"request_id": request_id},
        )
        yield f"event: error\ndata: {{\"reason\": \"{type(e).__name__}\"}}\n\n".encode()
    finally:
        await upstream_response.aclose()


def create_sse_proxy_router() -> APIRouter:
    """Create the SSE proxy router for streaming workspace events."""
    router = APIRouter(tags=["sse-proxy"])

    @router.get("/w/{workspace_id}/{path:path}", response_model=None)
    async def sse_proxy(
        workspace_id: str,
        path: str,
        request: Request,
    ) -> StreamingResponse | JSONResponse:
        """Proxy SSE streams from workspace runtime.

        Only handles requests with Accept: text/event-stream.
        Other requests fall through to the regular HTTP proxy.
        """
        accept = request.headers.get("accept", "")
        if "text/event-stream" not in accept:
            return JSONResponse(
                status_code=406,
                content={"code": "NOT_SSE", "message": "Expected Accept: text/event-stream"},
            )

        request_id = getattr(request.state, "request_id", None)
        start_time = time.monotonic()

        logger.info(
            "SSE stream open: workspace=%s path=/%s",
            workspace_id,
            path,
            extra={"request_id": request_id},
        )

        deps = request.app.state.deps
        settings = request.app.state.settings

        # Workspace membership authz (AUTHZ0): require active membership before
        # exposing runtime readiness state or streaming data.
        from ..security.workspace_authz import get_request_user_id, require_workspace_membership

        user_id = get_request_user_id(request)
        await require_workspace_membership(workspace_id, user_id, deps)

        # Resolve runtime.
        runtime = await deps.runtime_store.get_runtime(workspace_id)
        if runtime is None:
            return JSONResponse(
                status_code=404,
                content={"code": "WORKSPACE_NOT_FOUND", "request_id": request_id},
            )

        runtime_state = runtime.get("state", "unknown")
        if runtime_state != "ready":
            return JSONResponse(
                status_code=503,
                content={
                    "code": "WORKSPACE_NOT_READY",
                    "state": runtime_state,
                    "request_id": request_id,
                },
            )

        sandbox_name = runtime.get("sandbox_name", "")
        if not sandbox_name or not _is_valid_sandbox_name(sandbox_name):
            return JSONResponse(
                status_code=502,
                content={"code": "RUNTIME_CONFIG_ERROR", "request_id": request_id},
            )

        if not settings.sprite_bearer_token:
            return JSONResponse(
                status_code=502,
                content={"code": "PROXY_CONFIG_ERROR", "request_id": request_id},
            )

        target_path = f"/{path}" if path else "/"
        target_url = _build_runtime_url(sandbox_name, target_path)

        incoming_headers = dict(request.headers)
        forwarded_headers = _sanitize_request_headers(
            incoming_headers,
            sprite_bearer_token=settings.sprite_bearer_token,
            request_id=request_id,
            session_id=incoming_headers.get("x-session-id"),
        )
        forwarded_headers["Accept"] = "text/event-stream"

        # Open streaming connection to upstream.
        http_client = httpx.AsyncClient()
        try:
            upstream_response = await http_client.send(
                http_client.build_request(
                    "GET",
                    target_url,
                    headers=forwarded_headers,
                    params=dict(request.query_params),
                ),
                stream=True,
            )
        except httpx.ConnectError:
            await http_client.aclose()
            return JSONResponse(
                status_code=502,
                content={"code": "RUNTIME_UNAVAILABLE", "request_id": request_id},
            )
        except httpx.TimeoutException:
            await http_client.aclose()
            return JSONResponse(
                status_code=504,
                content={"code": "PROXY_TIMEOUT", "request_id": request_id},
            )

        if upstream_response.status_code != 200:
            body = await upstream_response.aread()
            await upstream_response.aclose()
            await http_client.aclose()
            return JSONResponse(
                status_code=upstream_response.status_code,
                content={"code": "UPSTREAM_ERROR", "request_id": request_id},
            )

        async def event_generator() -> AsyncGenerator[bytes, None]:
            try:
                async for chunk in _stream_sse_events(
                    upstream_response,
                    request_id=request_id,
                ):
                    yield chunk
            finally:
                duration = time.monotonic() - start_time
                logger.info(
                    "SSE stream closed: workspace=%s duration=%.1fs",
                    workspace_id,
                    duration,
                    extra={"request_id": request_id},
                )
                await http_client.aclose()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id or "",
            },
        )

    return router
