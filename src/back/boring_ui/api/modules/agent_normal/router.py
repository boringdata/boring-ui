"""agent-normal HTTP router (runtime-only session lifecycle)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from ...config import APIConfig
from ..pty.lifecycle import list_pty_session_summaries
from ..stream import get_session_registry as get_stream_registry


def _list_stream_session_summaries() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for session_id, session in get_stream_registry().items():
        sessions.append(
            {
                "id": session_id,
                "type": "stream",
                "alive": session.is_alive(),
                "clients": len(session.clients),
                "history_count": len(session.history),
            }
        )
    return sessions


def create_agent_normal_router(config: APIConfig | None = None) -> APIRouter:
    """Create agent-normal router.

    Note: config is reserved for future policy/claims enforcement; this bead
    only migrates route family + delegation wiring.
    """
    _ = config
    router = APIRouter(tags=["agent-normal"])

    @router.get("/sessions")
    async def list_sessions() -> dict[str, Any]:
        """List active PTY + stream sessions.

        PTY listing is delegated to pty-service.
        """
        pty_sessions = list_pty_session_summaries()
        stream_sessions = _list_stream_session_summaries()
        return {"sessions": pty_sessions + stream_sessions}

    @router.post("/sessions")
    async def create_session() -> dict[str, str]:
        """Create a new session ID (client will connect via WebSocket)."""
        return {"session_id": str(uuid.uuid4())}

    return router

