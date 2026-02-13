"""Session workspace selection route.

Bead: bd-1joj.6 (SESS0)

Implements POST /api/v1/session/workspace per section 11.1:
  - Validates workspace exists and user has active membership
  - Reads runtime_state from RuntimeMetadataStore
  - Sets active workspace in signed session cookie
  - Returns workspace_id, role, runtime_state, next_path

User identity is resolved from:
  1. X-User-ID header (local dev / testing)
  2. Will be replaced by Supabase JWT decoding in AUTH0
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _sign_cookie(payload: dict[str, Any], secret: str) -> str:
    """Create a signed cookie value: base64(json) + '.' + hmac_signature."""
    data = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{sig}"


def _verify_cookie(value: str, secret: str) -> dict[str, Any] | None:
    """Verify and decode a signed cookie. Returns None if invalid."""
    parts = value.rsplit(".", 1)
    if len(parts) != 2:
        return None
    data, sig = parts
    expected_sig = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(data))
    except (json.JSONDecodeError, ValueError):
        return None


def _get_user_id(request: Request) -> str | None:
    """Extract user identity from request.

    For local dev/testing, reads X-User-ID header.
    AUTH0 will replace this with Supabase JWT decoding.
    """
    return request.headers.get("x-user-id")


def create_session_router() -> APIRouter:
    """Create the session management router."""
    router = APIRouter(prefix="/api/v1", tags=["session"])

    @router.post("/session/workspace")
    async def set_session_workspace(request: Request) -> JSONResponse:
        """Select the active workspace for this session."""
        user_id = _get_user_id(request)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={
                    "code": "AUTH_REQUIRED",
                    "message": "User identity required",
                },
            )

        # Parse request body
        try:
            body = await request.json()
            workspace_id = body.get("workspace_id")
        except Exception:
            return JSONResponse(
                status_code=400,
                content={
                    "code": "INVALID_REQUEST",
                    "message": "Request body must contain workspace_id",
                },
            )

        if not workspace_id:
            return JSONResponse(
                status_code=400,
                content={
                    "code": "INVALID_REQUEST",
                    "message": "workspace_id is required",
                },
            )

        deps = request.app.state.deps
        settings = request.app.state.settings

        # 1. Validate workspace exists
        workspace = await deps.workspace_repo.get(workspace_id)
        if workspace is None:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "WORKSPACE_NOT_FOUND",
                    "message": f"Workspace {workspace_id} not found",
                },
            )

        # 2. Validate active membership
        membership = await deps.member_repo.get_membership(workspace_id, user_id)
        if membership is None:
            return JSONResponse(
                status_code=403,
                content={
                    "code": "FORBIDDEN",
                    "message": "Not an active member of this workspace",
                },
            )

        role = membership.get("role", "admin")

        # 3. Read runtime state
        runtime = await deps.runtime_store.get_runtime(workspace_id)
        runtime_state = runtime.get("state", "provisioning") if runtime else "provisioning"

        # 4. Set active workspace in session cookie
        session_secret = settings.session_secret or "local-dev-secret"
        cookie_payload = {
            "active_workspace_id": workspace_id,
            "user_id": user_id,
        }
        cookie_value = _sign_cookie(cookie_payload, session_secret)

        response = JSONResponse(
            status_code=200,
            content={
                "workspace_id": workspace_id,
                "role": role,
                "runtime_state": runtime_state,
                "next_path": f"/w/{workspace_id}/app",
            },
        )

        # Set cookie with proper flags per plan section 13.1
        is_secure = not settings.is_local
        response.set_cookie(
            key="boring-session",
            value=cookie_value,
            httponly=True,
            secure=is_secure,
            samesite="lax",
            path="/",
        )

        return response

    return router
