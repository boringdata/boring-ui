"""Canonical user identity/settings routes owned by boring-ui control-plane."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from ...config import APIConfig
from ...policy import enforce_delegated_policy_or_none
from .auth_session import SessionExpired, SessionInvalid, parse_session_cookie
from .user_settings_state import (
    build_me_payload,
    read_user_settings,
    touch_user_profile,
    user_state_service,
    write_user_settings,
)


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or uuid4())


def _error(
    request: Request,
    *,
    status_code: int,
    error: str,
    code: str,
    message: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "code": code,
            "message": message,
            "request_id": _request_id(request),
        },
    )

def _load_session(request: Request, config: APIConfig):
    token = request.cookies.get(config.auth_session_cookie_name, "")
    if not token:
        return _error(
            request,
            status_code=401,
            error="unauthorized",
            code="SESSION_REQUIRED",
            message="No active session",
        )
    try:
        return parse_session_cookie(token, secret=config.auth_session_secret)
    except SessionExpired:
        return _error(
            request,
            status_code=401,
            error="unauthorized",
            code="SESSION_EXPIRED",
            message="Session expired",
        )
    except SessionInvalid:
        return _error(
            request,
            status_code=401,
            error="unauthorized",
            code="SESSION_INVALID",
            message="Session invalid",
        )

def create_me_router(config: APIConfig) -> APIRouter:
    """Create canonical `/api/v1/me` routes."""

    router = APIRouter(tags=["user"])
    service = user_state_service(config)

    @router.get("/me")
    def get_me(request: Request):
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.read"},
            operation="workspace-core.user.me.get",
        )
        if deny is not None:
            return deny

        session_or_error = _load_session(request, config)
        if isinstance(session_or_error, JSONResponse):
            return session_or_error
        session = session_or_error

        merged_user = touch_user_profile(service, user_id=session.user_id, email=session.email)
        return build_me_payload(merged_user)

    @router.get("/me/settings")
    def get_me_settings(request: Request):
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.read"},
            operation="workspace-core.user.settings.get",
        )
        if deny is not None:
            return deny

        session_or_error = _load_session(request, config)
        if isinstance(session_or_error, JSONResponse):
            return session_or_error
        session = session_or_error

        settings = read_user_settings(service, session.user_id)
        return {"ok": True, "settings": settings}

    @router.put("/me/settings")
    def put_me_settings(
        request: Request,
        body: dict[str, Any] | None = Body(default=None),
    ):
        deny = enforce_delegated_policy_or_none(
            request,
            {"workspace.files.write"},
            operation="workspace-core.user.settings.update",
        )
        if deny is not None:
            return deny

        session_or_error = _load_session(request, config)
        if isinstance(session_or_error, JSONResponse):
            return session_or_error
        session = session_or_error

        settings = write_user_settings(
            service,
            user_id=session.user_id,
            email=session.email,
            settings=dict(body or {}),
        )
        return {"ok": True, "settings": settings}

    return router
