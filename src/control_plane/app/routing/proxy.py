"""Workspace HTTP proxy for forwarding /w/{workspace_id}/... to Sprite runtime.

Bead: bd-1joj.18 (PROXY0)

This module implements the control-plane proxy that forwards browser requests
to the correct Sprite sandbox runtime. The proxy:

1. Resolves workspace runtime metadata from Supabase
2. Verifies the runtime is in "ready" state
3. Strips the /w/{workspace_id} prefix
4. Injects the Sprite bearer token server-side (NEVER from browser)
5. Strips spoofed auth headers from browser requests
6. Forwards via httpx.AsyncClient
7. Strips internal headers from the response

Security model (section 13.3):
- Workspace plane does NOT trust browser identity
- Only accepts control-plane proxied requests with valid server-side bearer
- Browser never receives Sprite bearer token
"""

from __future__ import annotations

import logging
import re

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Headers that MUST be stripped from browser requests before forwarding.
# These could be spoofed by a malicious client to impersonate the control plane.
STRIP_REQUEST_HEADERS: frozenset[str] = frozenset({
    "authorization",
    "x-sprite-token",
    "x-service-token",
    "x-internal-auth",
})

# Headers to strip from the runtime response before returning to browser.
# These are internal implementation details of the Sprite sandbox.
# set-cookie is stripped to prevent the workspace plane from setting
# cookies on the control-plane domain.
STRIP_RESPONSE_HEADERS: frozenset[str] = frozenset({
    "x-sprite-token",
    "x-service-token",
    "x-internal-auth",
    "server",
    "set-cookie",
})

# Headers that should NOT be forwarded (hop-by-hop per HTTP spec).
HOP_BY_HOP_HEADERS: frozenset[str] = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
})

# Route prefixes that are valid workspace-plane targets (section 5.3).
WORKSPACE_ROUTE_PREFIXES: tuple[str, ...] = (
    "/app",
    "/api/v1/files",
    "/api/v1/git",
    "/api/v1/pty",
    "/api/v1/agent/sessions",
)


# Sandbox names must be alphanumeric + hyphens only to prevent URL injection.
_SANDBOX_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def _is_valid_sandbox_name(name: str) -> bool:
    return bool(_SANDBOX_NAME_RE.match(name))


def _build_runtime_url(sandbox_name: str, path: str) -> str:
    """Construct the target URL for a Sprite sandbox.

    The URL pattern follows the Sprites HTTP endpoint convention.
    """
    return f"https://{sandbox_name}.sprites.dev{path}"


def _sanitize_request_headers(
    headers: dict[str, str],
    sprite_bearer_token: str,
    request_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, str]:
    """Build forwarded headers: strip dangerous headers, inject auth."""
    forwarded: dict[str, str] = {}

    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in STRIP_REQUEST_HEADERS:
            continue
        if lower_key in HOP_BY_HOP_HEADERS:
            continue
        # Don't forward host header — the proxy sets its own.
        if lower_key == "host":
            continue
        forwarded[key] = value

    # Inject server-side Sprite auth (NEVER from browser).
    forwarded["Authorization"] = f"Bearer {sprite_bearer_token}"

    # Propagate request ID.
    if request_id:
        forwarded["X-Request-ID"] = request_id

    # Propagate session ID if present.
    if session_id:
        forwarded["X-Session-ID"] = session_id

    return forwarded


def _sanitize_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Strip internal headers from the runtime response."""
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in STRIP_RESPONSE_HEADERS:
            continue
        if lower_key in HOP_BY_HOP_HEADERS:
            continue
        sanitized[key] = value
    return sanitized


def create_workspace_proxy_router() -> APIRouter:
    """Create the /w/{workspace_id}/... proxy router."""
    router = APIRouter(tags=["workspace-proxy"])

    @router.api_route(
        "/w/{workspace_id}/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    )
    async def proxy_to_workspace(
        workspace_id: str,
        path: str,
        request: Request,
    ) -> Response:
        """Proxy a request to the workspace's Sprite runtime."""
        request_id = getattr(request.state, "request_id", None)

        # ── 0. Workspace membership authz (AUTHZ0) ───────────────
        deps = request.app.state.deps
        settings = request.app.state.settings

        from ..security.workspace_authz import get_request_user_id, require_workspace_membership
        user_id = get_request_user_id(request)
        await require_workspace_membership(workspace_id, user_id, deps)

        # ── 1. Resolve runtime metadata ──────────────────────────

        runtime = await deps.runtime_store.get_runtime(workspace_id)
        if runtime is None:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "WORKSPACE_NOT_FOUND",
                    "message": f"No runtime found for workspace {workspace_id}",
                    "request_id": request_id,
                },
            )

        # ── 2. Verify runtime is ready ───────────────────────────
        runtime_state = runtime.get("state", "unknown")
        if runtime_state != "ready":
            return JSONResponse(
                status_code=503,
                content={
                    "code": "WORKSPACE_NOT_READY",
                    "message": f"Workspace runtime is {runtime_state}",
                    "workspace_id": workspace_id,
                    "state": runtime_state,
                    "request_id": request_id,
                },
            )

        # ── 3. Validate route is a workspace-plane target ────────
        target_path = f"/{path}" if path else "/"

        # Reject path traversal attempts.
        if ".." in target_path:
            return JSONResponse(
                status_code=400,
                content={
                    "code": "INVALID_PATH",
                    "message": "Path traversal is not allowed",
                    "request_id": request_id,
                },
            )

        if not any(target_path.startswith(prefix) for prefix in WORKSPACE_ROUTE_PREFIXES):
            return JSONResponse(
                status_code=404,
                content={
                    "code": "ROUTE_NOT_FOUND",
                    "message": f"Path /{path} is not a workspace-plane route",
                    "request_id": request_id,
                },
            )

        # ── 4. Build target URL ──────────────────────────────────
        sandbox_name = runtime.get("sandbox_name", "")
        if not sandbox_name or not _is_valid_sandbox_name(sandbox_name):
            logger.error(
                "Runtime for %s has no sandbox_name",
                workspace_id,
                extra={"request_id": request_id},
            )
            return JSONResponse(
                status_code=502,
                content={
                    "code": "RUNTIME_CONFIG_ERROR",
                    "message": "Runtime has no sandbox name configured",
                    "request_id": request_id,
                },
            )

        target_url = _build_runtime_url(sandbox_name, target_path)

        # ── 5. Build forwarded headers ───────────────────────────
        if not settings.sprite_bearer_token:
            logger.error(
                "sprite_bearer_token not configured",
                extra={"request_id": request_id},
            )
            return JSONResponse(
                status_code=502,
                content={
                    "code": "PROXY_CONFIG_ERROR",
                    "message": "Sprite bearer token not configured",
                    "request_id": request_id,
                },
            )

        incoming_headers = dict(request.headers)
        session_id = incoming_headers.get("x-session-id")

        forwarded_headers = _sanitize_request_headers(
            incoming_headers,
            sprite_bearer_token=settings.sprite_bearer_token,
            request_id=request_id,
            session_id=session_id,
        )

        # ── 6. Read request body ─────────────────────────────────
        body = await request.body()

        # ── 7. Forward to runtime ────────────────────────────────
        try:
            async with httpx.AsyncClient() as client:
                proxy_response = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=forwarded_headers,
                    content=body if body else None,
                    params=dict(request.query_params),
                    timeout=30.0,
                    follow_redirects=False,
                )
        except httpx.TimeoutException:
            logger.warning(
                "Proxy timeout for %s -> %s",
                workspace_id,
                target_url,
                extra={"request_id": request_id},
            )
            return JSONResponse(
                status_code=504,
                content={
                    "code": "PROXY_TIMEOUT",
                    "message": "Workspace runtime did not respond in time",
                    "request_id": request_id,
                },
            )
        except httpx.ConnectError:
            logger.warning(
                "Proxy connect error for %s -> %s",
                workspace_id,
                target_url,
                extra={"request_id": request_id},
            )
            return JSONResponse(
                status_code=502,
                content={
                    "code": "RUNTIME_UNAVAILABLE",
                    "message": "Could not connect to workspace runtime",
                    "request_id": request_id,
                },
            )

        # ── 8. Build response ────────────────────────────────────
        response_headers = _sanitize_response_headers(proxy_response.headers)

        return Response(
            content=proxy_response.content,
            status_code=proxy_response.status_code,
            headers=response_headers,
        )

    return router
