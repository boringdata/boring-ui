"""Workspace-scoped agent session create endpoint.

Bead: bd-223o.13.1 (G1)

Implements the agent session create contract from Feature 3 design doc
section 14.2:

  POST /w/{workspace_id}/api/v1/agent/sessions
  → 201 { session_id, workspace_id, created_by, created_at }

Membership validation:
  - Caller must be authenticated (AuthIdentity).
  - Caller must be an active member of the workspace.
  - Non-members receive 403 forbidden.

Session ID contract (section 14.2):
  - session_id is required for agent stream lifecycle endpoints.
  - Session is workspace-scoped — cannot be used across workspaces.

This module provides:
  1. ``AgentSession`` — domain model for a workspace agent session.
  2. ``AgentSessionRepository`` — abstract storage protocol.
  3. ``InMemoryAgentSessionRepository`` — test implementation.
  4. ``create_agent_session_router`` — FastAPI router factory.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from control_plane.app.security.auth_guard import get_auth_identity
from control_plane.app.security.token_verify import AuthIdentity


# ── Domain model ──────────────────────────────────────────────────────


@dataclass
class AgentSession:
    """Agent session domain object.

    Attributes:
        id: Unique session identifier.
        workspace_id: Workspace this session belongs to.
        created_by: User ID who created the session.
        created_at: Creation timestamp.
        stopped_at: When the session was stopped (None if active).
    """

    id: str
    workspace_id: str
    created_by: str
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    stopped_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.stopped_at is None


# ── Membership checker protocol ──────────────────────────────────────


class MembershipChecker(Protocol):
    """Check if a user is an active member of a workspace."""

    async def is_active_member(
        self, workspace_id: str, user_id: str,
    ) -> bool: ...


# ── Repository protocol ──────────────────────────────────────────────


class AgentSessionRepository(Protocol):
    """Abstract agent session storage."""

    async def create(self, session: AgentSession) -> AgentSession: ...
    async def get(self, session_id: str) -> AgentSession | None: ...
    async def list_for_workspace(
        self, workspace_id: str,
    ) -> list[AgentSession]: ...
    async def stop(self, session_id: str) -> AgentSession | None: ...


# ── In-memory implementations ────────────────────────────────────────


class InMemoryAgentSessionRepository:
    """Simple in-memory agent session store for testing."""

    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}

    async def create(self, session: AgentSession) -> AgentSession:
        self._sessions[session.id] = session
        return session

    async def get(self, session_id: str) -> AgentSession | None:
        return self._sessions.get(session_id)

    async def list_for_workspace(
        self, workspace_id: str,
    ) -> list[AgentSession]:
        return sorted(
            [s for s in self._sessions.values()
             if s.workspace_id == workspace_id],
            key=lambda s: s.created_at,
        )

    async def stop(self, session_id: str) -> AgentSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.stopped_at is None:
            session.stopped_at = datetime.now(timezone.utc)
        return session


class InMemoryMembershipChecker:
    """Test membership checker backed by a set of (workspace_id, user_id)."""

    def __init__(self, members: set[tuple[str, str]] | None = None) -> None:
        self._members: set[tuple[str, str]] = members or set()

    def add_member(self, workspace_id: str, user_id: str) -> None:
        self._members.add((workspace_id, user_id))

    async def is_active_member(
        self, workspace_id: str, user_id: str,
    ) -> bool:
        return (workspace_id, user_id) in self._members


# ── Request schemas ──────────────────────────────────────────────────


class CreateSessionRequest(BaseModel):
    """Optional metadata for session creation."""

    model: str | None = Field(default=None, description='Agent model name')


# ── Route factory ────────────────────────────────────────────────────


def create_agent_session_router(
    session_repo: AgentSessionRepository,
    membership: MembershipChecker,
) -> APIRouter:
    """Create agent session router with injected dependencies.

    Args:
        session_repo: Agent session repository.
        membership: Membership checker for authorization.

    Returns:
        FastAPI router with session lifecycle routes.
    """
    router = APIRouter(tags=['agent-sessions'])

    @router.post(
        '/w/{workspace_id}/api/v1/agent/sessions',
        status_code=201,
    )
    async def create_session(
        workspace_id: str,
        identity: AuthIdentity = Depends(get_auth_identity),
        body: CreateSessionRequest | None = None,
    ):
        """Create a new agent session in the workspace.

        Requires active workspace membership.
        Returns 201 with session metadata.
        """
        # Membership gate.
        if not await membership.is_active_member(
            workspace_id, identity.user_id,
        ):
            return JSONResponse(
                status_code=403,
                content={
                    'error': 'forbidden',
                    'detail': 'Not an active member of this workspace.',
                },
            )

        session_id = f'sess_{uuid.uuid4().hex[:16]}'
        session = AgentSession(
            id=session_id,
            workspace_id=workspace_id,
            created_by=identity.user_id,
        )
        await session_repo.create(session)

        return {
            'session_id': session.id,
            'workspace_id': session.workspace_id,
            'created_by': session.created_by,
            'created_at': session.created_at.isoformat(),
        }

    @router.get('/w/{workspace_id}/api/v1/agent/sessions')
    async def list_sessions(
        workspace_id: str,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """List agent sessions for a workspace."""
        if not await membership.is_active_member(
            workspace_id, identity.user_id,
        ):
            return JSONResponse(
                status_code=403,
                content={
                    'error': 'forbidden',
                    'detail': 'Not an active member of this workspace.',
                },
            )

        sessions = await session_repo.list_for_workspace(workspace_id)
        return {
            'sessions': [
                {
                    'session_id': s.id,
                    'workspace_id': s.workspace_id,
                    'created_by': s.created_by,
                    'created_at': s.created_at.isoformat(),
                    'is_active': s.is_active,
                }
                for s in sessions
            ],
        }

    @router.post('/w/{workspace_id}/api/v1/agent/sessions/{session_id}/stop')
    async def stop_session(
        workspace_id: str,
        session_id: str,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Stop an agent session. Idempotent."""
        if not await membership.is_active_member(
            workspace_id, identity.user_id,
        ):
            return JSONResponse(
                status_code=403,
                content={
                    'error': 'forbidden',
                    'detail': 'Not an active member of this workspace.',
                },
            )

        session = await session_repo.get(session_id)
        if session is None or session.workspace_id != workspace_id:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'session_not_found',
                    'detail': f'Session {session_id!r} not found.',
                },
            )

        stopped = await session_repo.stop(session_id)
        return {
            'session_id': stopped.id,
            'stopped_at': stopped.stopped_at.isoformat(),
            'is_active': stopped.is_active,
        }

    return router
