"""Workspace CRUD endpoints.

Bead: bd-223o.9.1 (C1)

Implements app-scoped workspace create, list, get, and patch with
strict request validation. All endpoints require authentication.

Design doc references:
  - Section 11 endpoints 4-7 (CRUD)
  - Section 12 schema (cloud.workspaces table)
  - Section 18.3 acceptance criteria

Response contracts:
  POST /api/v1/workspaces → 202 { workspace_id, app_id, ... }
  GET  /api/v1/workspaces → 200 { workspaces: [...] }
  GET  /api/v1/workspaces/{id} → 200 { workspace_id, name, ... }
  PATCH /api/v1/workspaces/{id} → 200 { workspace_id, name, ... }
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


# ── Domain models ─────────────────────────────────────────────────────


@dataclass
class Workspace:
    """Workspace domain object matching cloud.workspaces schema."""

    id: str
    name: str
    app_id: str
    created_by: str
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Repository protocol ──────────────────────────────────────────────


class WorkspaceRepository(Protocol):
    """Abstract workspace storage.

    Implementations: InMemoryWorkspaceRepository (testing),
    SupabaseWorkspaceRepository (production).
    """

    async def create(self, workspace: Workspace) -> Workspace: ...
    async def get(self, workspace_id: str) -> Workspace | None: ...
    async def list_for_user(
        self, user_id: str, app_id: str,
    ) -> list[Workspace]: ...
    async def update(
        self, workspace_id: str, **fields,
    ) -> Workspace | None: ...
    async def exists_name(
        self, name: str, app_id: str,
    ) -> bool: ...


# ── In-memory implementation (for testing) ────────────────────────────


class InMemoryWorkspaceRepository:
    """Simple in-memory workspace store for testing."""

    def __init__(self) -> None:
        self._workspaces: dict[str, Workspace] = {}
        # Track creator memberships: workspace_id -> set of user_ids
        self._members: dict[str, set[str]] = {}

    async def create(self, workspace: Workspace) -> Workspace:
        self._workspaces[workspace.id] = workspace
        self._members.setdefault(workspace.id, set()).add(
            workspace.created_by,
        )
        return workspace

    async def get(self, workspace_id: str) -> Workspace | None:
        return self._workspaces.get(workspace_id)

    async def list_for_user(
        self, user_id: str, app_id: str,
    ) -> list[Workspace]:
        result = []
        for ws in self._workspaces.values():
            if ws.app_id != app_id:
                continue
            members = self._members.get(ws.id, set())
            if user_id in members:
                result.append(ws)
        return sorted(result, key=lambda w: w.created_at)

    async def update(
        self, workspace_id: str, **fields,
    ) -> Workspace | None:
        ws = self._workspaces.get(workspace_id)
        if ws is None:
            return None
        for k, v in fields.items():
            if hasattr(ws, k):
                object.__setattr__(ws, k, v)
        ws.updated_at = datetime.now(timezone.utc)
        return ws

    async def exists_name(self, name: str, app_id: str) -> bool:
        return any(
            ws.name == name and ws.app_id == app_id
            for ws in self._workspaces.values()
        )


# ── Request/response schemas ──────────────────────────────────────────


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    app_id: str = Field(default='boring-ui')


class PatchWorkspaceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)


# ── Route factory ─────────────────────────────────────────────────────


def create_workspace_router(
    repo: WorkspaceRepository,
    default_app_id: str = 'boring-ui',
) -> APIRouter:
    """Create workspace CRUD router with injected repository.

    Args:
        repo: Workspace repository implementation.
        default_app_id: Default app_id for workspace listing.

    Returns:
        FastAPI router with workspace CRUD routes.
    """
    router = APIRouter(tags=['workspaces'])

    @router.post('/api/v1/workspaces', status_code=202)
    async def create_workspace(
        body: CreateWorkspaceRequest,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Create a new workspace.

        Returns 202 with workspace metadata. The workspace starts in
        a pre-provisioning state; actual provisioning is triggered
        separately (Epic D).
        """
        # Check for duplicate name within app scope.
        if await repo.exists_name(body.name, body.app_id):
            return JSONResponse(
                status_code=409,
                content={
                    'error': 'workspace_exists',
                    'detail': (
                        f'A workspace named {body.name!r} '
                        f'already exists for app {body.app_id!r}.'
                    ),
                },
            )

        workspace_id = f'ws_{uuid.uuid4().hex[:12]}'
        workspace = Workspace(
            id=workspace_id,
            name=body.name,
            app_id=body.app_id,
            created_by=identity.user_id,
        )
        await repo.create(workspace)

        return {
            'workspace_id': workspace.id,
            'name': workspace.name,
            'app_id': workspace.app_id,
            'created_by': workspace.created_by,
            'created_at': workspace.created_at.isoformat(),
        }

    @router.get('/api/v1/workspaces')
    async def list_workspaces(
        identity: AuthIdentity = Depends(get_auth_identity),
        app_id: str = default_app_id,
    ):
        """List workspaces the authenticated user is a member of."""
        workspaces = await repo.list_for_user(
            identity.user_id, app_id,
        )
        return {
            'workspaces': [
                {
                    'workspace_id': ws.id,
                    'name': ws.name,
                    'app_id': ws.app_id,
                    'created_at': ws.created_at.isoformat(),
                }
                for ws in workspaces
            ],
        }

    @router.get('/api/v1/workspaces/{workspace_id}')
    async def get_workspace(
        workspace_id: str,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Get a single workspace by ID."""
        workspace = await repo.get(workspace_id)
        if workspace is None:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'workspace_not_found',
                    'detail': f'Workspace {workspace_id!r} not found.',
                },
            )

        return {
            'workspace_id': workspace.id,
            'name': workspace.name,
            'app_id': workspace.app_id,
            'created_by': workspace.created_by,
            'created_at': workspace.created_at.isoformat(),
            'updated_at': workspace.updated_at.isoformat(),
        }

    @router.patch('/api/v1/workspaces/{workspace_id}')
    async def patch_workspace(
        workspace_id: str,
        body: PatchWorkspaceRequest,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Update workspace fields (currently only name)."""
        workspace = await repo.get(workspace_id)
        if workspace is None:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'workspace_not_found',
                    'detail': f'Workspace {workspace_id!r} not found.',
                },
            )

        updates = {}
        if body.name is not None:
            # Check name uniqueness within app scope.
            if body.name != workspace.name and await repo.exists_name(
                body.name, workspace.app_id,
            ):
                return JSONResponse(
                    status_code=409,
                    content={
                        'error': 'workspace_exists',
                        'detail': (
                            f'A workspace named {body.name!r} '
                            f'already exists for app {workspace.app_id!r}.'
                        ),
                    },
                )
            updates['name'] = body.name

        if not updates:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'invalid_request',
                    'detail': 'No fields to update.',
                },
            )

        updated = await repo.update(workspace_id, **updates)

        return {
            'workspace_id': updated.id,
            'name': updated.name,
            'app_id': updated.app_id,
            'updated_at': updated.updated_at.isoformat(),
        }

    return router
