"""pty-service HTTP lifecycle endpoints.

Kept separate from the PTY WebSocket router so it can be mounted under the
canonical `/api/v1/pty/*` family.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from ...config import APIConfig
from .service import get_session_registry


def list_pty_session_summaries() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for session_id, session in get_session_registry().items():
        sessions.append(
            {
                "id": session_id,
                "type": "pty",
                "alive": session.is_alive(),
                "clients": len(session.clients),
                "history_count": len(session.history),
            }
        )
    return sessions


def create_pty_lifecycle_router(config: APIConfig | None = None) -> APIRouter:
    _ = config
    router = APIRouter(tags=["pty"])

    @router.get("/sessions")
    async def list_sessions() -> dict[str, Any]:
        return {"sessions": list_pty_session_summaries()}

    @router.post("/sessions")
    async def create_session() -> dict[str, str]:
        return {"session_id": str(uuid.uuid4())}

    return router

