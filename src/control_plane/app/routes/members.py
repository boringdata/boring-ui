"""Workspace membership and invite endpoints.

Bead: bd-223o.9.2 (C2)

Implements invite create, member list, and soft-removal with status
transition semantics (pending → active → removed).

Design doc references:
  - Section 11 endpoints 8-10 (membership)
  - Section 12 schema (cloud.workspace_members table)
  - Section 18.2 acceptance criteria

Response contracts:
  POST   /api/v1/workspaces/{id}/members → 201 { email, role, status }
  GET    /api/v1/workspaces/{id}/members → 200 { members: [...] }
  DELETE /api/v1/workspaces/{id}/members/{member_id} → 200 { status: removed }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from control_plane.app.security.auth_guard import get_auth_identity
from control_plane.app.security.token_verify import AuthIdentity


# ── Domain models ─────────────────────────────────────────────────────


@dataclass
class Member:
    """Workspace member matching cloud.workspace_members schema."""

    id: int
    workspace_id: str
    user_id: str | None
    email: str
    role: str = 'admin'
    status: str = 'pending'
    invited_by: str | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Repository protocol ──────────────────────────────────────────────


class MemberRepository(Protocol):
    """Abstract workspace membership storage."""

    async def create(self, member: Member) -> Member: ...
    async def get(self, member_id: int) -> Member | None: ...
    async def list_for_workspace(
        self, workspace_id: str, include_removed: bool = False,
    ) -> list[Member]: ...
    async def has_active_or_pending(
        self, workspace_id: str, email: str,
    ) -> bool: ...
    async def soft_remove(self, member_id: int) -> Member | None: ...
    async def is_member(
        self, workspace_id: str, user_id: str,
    ) -> bool: ...
    async def auto_accept_pending(
        self, email: str, user_id: str,
    ) -> list[Member]: ...


# ── In-memory implementation ──────────────────────────────────────────


class InMemoryMemberRepository:
    """Simple in-memory member store for testing."""

    def __init__(self) -> None:
        self._members: dict[int, Member] = {}
        self._next_id = 1

    async def create(self, member: Member) -> Member:
        member.id = self._next_id
        self._next_id += 1
        self._members[member.id] = member
        return member

    async def get(self, member_id: int) -> Member | None:
        return self._members.get(member_id)

    async def list_for_workspace(
        self, workspace_id: str, include_removed: bool = False,
    ) -> list[Member]:
        result = []
        for m in self._members.values():
            if m.workspace_id != workspace_id:
                continue
            if not include_removed and m.status == 'removed':
                continue
            result.append(m)
        return sorted(result, key=lambda m: m.created_at)

    async def has_active_or_pending(
        self, workspace_id: str, email: str,
    ) -> bool:
        normalized = email.lower()
        return any(
            m.workspace_id == workspace_id
            and m.email.lower() == normalized
            and m.status in ('pending', 'active')
            for m in self._members.values()
        )

    async def soft_remove(self, member_id: int) -> Member | None:
        m = self._members.get(member_id)
        if m is None:
            return None
        m.status = 'removed'
        m.updated_at = datetime.now(timezone.utc)
        return m

    async def is_member(
        self, workspace_id: str, user_id: str,
    ) -> bool:
        return any(
            m.workspace_id == workspace_id
            and m.user_id == user_id
            and m.status == 'active'
            for m in self._members.values()
        )

    async def auto_accept_pending(
        self, email: str, user_id: str,
    ) -> list[Member]:
        """Auto-accept all pending invites matching email.

        Transitions pending → active, sets user_id on the member record.
        Returns the list of newly-accepted memberships.
        """
        normalized = email.lower()
        accepted: list[Member] = []
        for m in self._members.values():
            if (
                m.email.lower() == normalized
                and m.status == 'pending'
            ):
                m.status = 'active'
                m.user_id = user_id
                m.updated_at = datetime.now(timezone.utc)
                accepted.append(m)
        return accepted


# ── Request/response schemas ──────────────────────────────────────────


class InviteMemberRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    role: str = Field(default='admin')

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError('Invalid email address')
        return v

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ('admin',):
            raise ValueError('V0 only supports admin role')
        return v


# ── Route factory ─────────────────────────────────────────────────────


def create_member_router(
    member_repo: MemberRepository,
    workspace_exists_fn=None,
) -> APIRouter:
    """Create membership CRUD router.

    Args:
        member_repo: Member repository implementation.
        workspace_exists_fn: Async callable(workspace_id) -> bool to verify
            workspace existence. If None, workspace check is skipped.
    """
    router = APIRouter(tags=['members'])

    async def _check_workspace(workspace_id: str) -> bool:
        """Return True if workspace exists or check is disabled."""
        if workspace_exists_fn is None:
            return True
        return await workspace_exists_fn(workspace_id)

    @router.post(
        '/api/v1/workspaces/{workspace_id}/members',
        status_code=201,
    )
    async def invite_member(
        workspace_id: str,
        body: InviteMemberRequest,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Invite a member to a workspace.

        Creates a pending membership record. If the email matches an
        existing user, auto-accept happens on first workspace list load
        (Epic C3).
        """
        if not await _check_workspace(workspace_id):
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'workspace_not_found',
                    'detail': f'Workspace {workspace_id!r} not found.',
                },
            )

        # Check for duplicate active/pending invite.
        if await member_repo.has_active_or_pending(
            workspace_id, body.email,
        ):
            return JSONResponse(
                status_code=409,
                content={
                    'error': 'duplicate_invite',
                    'detail': (
                        f'An active or pending invite for {body.email!r} '
                        f'already exists in workspace {workspace_id!r}.'
                    ),
                },
            )

        member = Member(
            id=0,  # assigned by repo
            workspace_id=workspace_id,
            user_id=None,  # resolved on auto-accept
            email=body.email,
            role=body.role,
            status='pending',
            invited_by=identity.user_id,
        )
        created = await member_repo.create(member)

        return {
            'member_id': created.id,
            'workspace_id': created.workspace_id,
            'email': created.email,
            'role': created.role,
            'status': created.status,
        }

    @router.get('/api/v1/workspaces/{workspace_id}/members')
    async def list_members(
        workspace_id: str,
        identity: AuthIdentity = Depends(get_auth_identity),
        include_removed: bool = False,
    ):
        """List members of a workspace."""
        if not await _check_workspace(workspace_id):
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'workspace_not_found',
                    'detail': f'Workspace {workspace_id!r} not found.',
                },
            )

        members = await member_repo.list_for_workspace(
            workspace_id, include_removed=include_removed,
        )

        return {
            'members': [
                {
                    'member_id': m.id,
                    'email': m.email,
                    'role': m.role,
                    'status': m.status,
                    'user_id': m.user_id,
                    'created_at': m.created_at.isoformat(),
                }
                for m in members
            ],
        }

    @router.delete(
        '/api/v1/workspaces/{workspace_id}/members/{member_id}',
    )
    async def remove_member(
        workspace_id: str,
        member_id: int,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Soft-remove a member from a workspace.

        Sets status to 'removed' rather than hard deleting.
        Preserves audit trail and allows potential re-invite.
        """
        member = await member_repo.get(member_id)
        if member is None or member.workspace_id != workspace_id:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'member_not_found',
                    'detail': (
                        f'Member {member_id} not found in '
                        f'workspace {workspace_id!r}.'
                    ),
                },
            )

        if member.status == 'removed':
            return JSONResponse(
                status_code=409,
                content={
                    'error': 'already_removed',
                    'detail': f'Member {member_id} is already removed.',
                },
            )

        removed = await member_repo.soft_remove(member_id)

        return {
            'member_id': removed.id,
            'workspace_id': removed.workspace_id,
            'email': removed.email,
            'status': removed.status,
        }

    return router
