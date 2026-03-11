"""Shared user identity/settings state helpers.

User settings are stored on the user profile record. Workspace settings remain
in the dedicated workspace-settings bucket and are intentionally separate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...config import APIConfig
from .repository import LocalControlPlaneRepository
from .service import ControlPlaneService


def user_state_service(config: APIConfig) -> ControlPlaneService:
    state_path = config.validate_path(config.control_plane_state_relpath)
    return ControlPlaneService(LocalControlPlaneRepository(state_path), workspace_root=config.workspace_root)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_me_payload(user: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "user_id": str(user.get("user_id", "")).strip(),
        "email": str(user.get("email", "")).strip().lower(),
        "display_name": str(user.get("display_name", "")).strip(),
    }
    return {
        "ok": True,
        **payload,
        "user": dict(payload),
        "me": dict(payload),
        "data": dict(payload),
    }


def find_user(service: ControlPlaneService, user_id: str) -> dict[str, Any] | None:
    return next(
        (user for user in service.list_users() if user.get("user_id") == user_id),
        None,
    )


def touch_user_profile(
    service: ControlPlaneService,
    *,
    user_id: str,
    email: str,
) -> dict[str, Any]:
    existing = find_user(service, user_id)
    return service.upsert_user(
        user_id,
        {
            "email": email,
            "display_name": str((existing or {}).get("display_name", "")).strip(),
            "settings": dict((existing or {}).get("settings") or {}),
            "last_seen_at": _now_iso(),
        },
    )


def read_user_settings(service: ControlPlaneService, user_id: str) -> dict[str, Any]:
    existing = find_user(service, user_id)
    return dict((existing or {}).get("settings") or {})


def write_user_settings(
    service: ControlPlaneService,
    *,
    user_id: str,
    email: str,
    settings: dict[str, Any],
) -> dict[str, Any]:
    existing = find_user(service, user_id)
    payload = dict(settings)
    service.upsert_user(
        user_id,
        {
            "email": email,
            "display_name": str(payload.get("display_name", (existing or {}).get("display_name", ""))).strip(),
            "settings": payload,
            "last_seen_at": _now_iso(),
        },
    )
    return payload
