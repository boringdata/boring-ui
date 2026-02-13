"""User session endpoints for active workspace tracking.

Bead: bd-223o.14.2 (H2)

Provides a minimal session store to persist the user's active workspace
selection across page loads. When a user visits the root domain without a
workspace path, the frontend can read active_workspace_id from the workspace
list response to redirect to the correct workspace.

Endpoint:
  PUT  /api/v1/session/active-workspace → 200 { active_workspace_id }
  GET  /api/v1/session/active-workspace → 200 { active_workspace_id }
"""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from control_plane.app.security.auth_guard import get_auth_identity
from control_plane.app.security.token_verify import AuthIdentity


# ── Repository protocol ──────────────────────────────────────────────


class SessionRepository(Protocol):
    """Abstract session storage for active workspace."""

    async def get_active_workspace(self, user_id: str) -> str | None: ...
    async def set_active_workspace(
        self, user_id: str, workspace_id: str,
    ) -> None: ...


# ── In-memory implementation (for testing) ────────────────────────────


class InMemorySessionRepository:
    """Simple in-memory session store for testing."""

    def __init__(self) -> None:
        self._active: dict[str, str] = {}

    async def get_active_workspace(self, user_id: str) -> str | None:
        return self._active.get(user_id)

    async def set_active_workspace(
        self, user_id: str, workspace_id: str,
    ) -> None:
        self._active[user_id] = workspace_id


# ── Request schema ────────────────────────────────────────────────────


class SetActiveWorkspaceRequest(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=128)


# ── Route factory ─────────────────────────────────────────────────────


def create_session_router(repo: SessionRepository) -> APIRouter:
    """Create session router with injected repository."""
    router = APIRouter(tags=['session'])

    @router.put('/api/v1/session/active-workspace')
    async def set_active_workspace(
        body: SetActiveWorkspaceRequest,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Set the active workspace for the authenticated user."""
        await repo.set_active_workspace(identity.user_id, body.workspace_id)
        return {'active_workspace_id': body.workspace_id}

    @router.get('/api/v1/session/active-workspace')
    async def get_active_workspace(
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Get the active workspace for the authenticated user."""
        workspace_id = await repo.get_active_workspace(identity.user_id)
        if workspace_id is None:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'no_active_workspace',
                    'detail': 'No active workspace set for this user.',
                },
            )
        return {'active_workspace_id': workspace_id}

    return router
