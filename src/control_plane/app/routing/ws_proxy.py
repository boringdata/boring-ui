"""WebSocket proxy for bidirectional forwarding to workspace runtime.

Bead: bd-1joj.19 (STREAM0)

Handles WebSocket connections for routes like /w/{workspace_id}/api/v1/pty/*.

The WebSocket proxy:
1. Accepts browser WebSocket connection
2. Opens upstream WebSocket to workspace runtime
3. Forwards messages bidirectionally
4. On either side close: close both sides cleanly
5. Forwards ping/pong for keep-alive
6. Enforces max message size
"""

from __future__ import annotations

import asyncio
import logging
import time

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .proxy import _build_runtime_url, _is_valid_sandbox_name

logger = logging.getLogger(__name__)

DEFAULT_MAX_MESSAGE_SIZE = 1 * 1024 * 1024  # 1MB


async def _forward_browser_to_upstream(
    browser_ws: WebSocket,
    upstream_ws: websockets.WebSocketClientProtocol,
    request_id: str | None,
    max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE,
) -> None:
    """Forward messages from browser WebSocket to upstream."""
    try:
        while True:
            data = await browser_ws.receive()
            if data.get("type") == "websocket.disconnect":
                break

            if "text" in data:
                msg = data["text"]
                if len(msg) > max_message_size:
                    logger.warning(
                        "WS message too large (%d bytes), dropping",
                        len(msg),
                        extra={"request_id": request_id},
                    )
                    continue
                await upstream_ws.send(msg)
            elif "bytes" in data:
                msg = data["bytes"]
                if len(msg) > max_message_size:
                    logger.warning(
                        "WS binary message too large (%d bytes), dropping",
                        len(msg),
                        extra={"request_id": request_id},
                    )
                    continue
                await upstream_ws.send(msg)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(
            "Browser->upstream forward ended: %s",
            e,
            extra={"request_id": request_id},
        )


async def _forward_upstream_to_browser(
    upstream_ws: websockets.WebSocketClientProtocol,
    browser_ws: WebSocket,
    request_id: str | None,
) -> None:
    """Forward messages from upstream WebSocket to browser."""
    try:
        async for message in upstream_ws:
            if isinstance(message, str):
                await browser_ws.send_text(message)
            elif isinstance(message, bytes):
                await browser_ws.send_bytes(message)
    except websockets.ConnectionClosed:
        pass
    except Exception as e:
        logger.debug(
            "Upstream->browser forward ended: %s",
            e,
            extra={"request_id": request_id},
        )


def create_ws_proxy_router() -> APIRouter:
    """Create the WebSocket proxy router for bidirectional workspace streams."""
    router = APIRouter(tags=["ws-proxy"])

    @router.websocket("/w/{workspace_id}/{path:path}")
    async def ws_proxy(
        websocket: WebSocket,
        workspace_id: str,
        path: str,
    ) -> None:
        """Proxy WebSocket connections to workspace runtime."""
        request_id = getattr(websocket.state, "request_id", None) if hasattr(websocket, "state") else None
        start_time = time.monotonic()

        deps = websocket.app.state.deps
        settings = websocket.app.state.settings

        # Resolve runtime.
        runtime = await deps.runtime_store.get_runtime(workspace_id)
        if runtime is None or runtime.get("state") != "ready":
            await websocket.close(code=1008, reason="workspace_not_ready")
            return

        sandbox_name = runtime.get("sandbox_name", "")
        if not sandbox_name or not _is_valid_sandbox_name(sandbox_name):
            await websocket.close(code=1008, reason="runtime_config_error")
            return

        if not settings.sprite_bearer_token:
            await websocket.close(code=1008, reason="proxy_config_error")
            return

        target_path = f"/{path}" if path else "/"
        target_url = _build_runtime_url(sandbox_name, target_path)
        # Convert https:// to wss:// for WebSocket.
        ws_target_url = target_url.replace("https://", "wss://").replace("http://", "ws://")

        logger.info(
            "WS proxy open: workspace=%s path=/%s",
            workspace_id,
            path,
            extra={"request_id": request_id},
        )

        # Accept browser connection.
        await websocket.accept()

        upstream_ws = None
        try:
            # Connect to upstream with Sprite auth.
            upstream_ws = await websockets.connect(
                ws_target_url,
                extra_headers={
                    "Authorization": f"Bearer {settings.sprite_bearer_token}",
                    "X-Request-ID": request_id or "",
                },
                max_size=DEFAULT_MAX_MESSAGE_SIZE,
            )

            # Run bidirectional forwarding concurrently.
            browser_to_upstream = asyncio.create_task(
                _forward_browser_to_upstream(
                    websocket, upstream_ws, request_id,
                )
            )
            upstream_to_browser = asyncio.create_task(
                _forward_upstream_to_browser(
                    upstream_ws, websocket, request_id,
                )
            )

            # Wait for either side to finish.
            done, pending = await asyncio.wait(
                [browser_to_upstream, upstream_to_browser],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the other direction.
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except websockets.InvalidStatusCode as e:
            logger.warning(
                "WS upstream rejected: status=%s",
                e.status_code,
                extra={"request_id": request_id},
            )
        except (ConnectionRefusedError, OSError) as e:
            logger.warning(
                "WS upstream connect failed: %s",
                e,
                extra={"request_id": request_id},
            )
        except Exception as e:
            logger.warning(
                "WS proxy error: %s",
                e,
                extra={"request_id": request_id},
            )
        finally:
            duration = time.monotonic() - start_time
            logger.info(
                "WS proxy closed: workspace=%s duration=%.1fs",
                workspace_id,
                duration,
                extra={"request_id": request_id},
            )
            # Close both sides.
            if upstream_ws is not None:
                try:
                    await upstream_ws.close()
                except Exception:
                    pass
            try:
                await websocket.close()
            except Exception:
                pass

    return router
