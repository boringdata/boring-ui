"""Unit tests for workspace authorization helper.

Bead: bd-1joj.12 (AUTHZ0)

Tests require_workspace_membership() logic directly against InMemory repos.
"""

from __future__ import annotations

import pytest

from fastapi import HTTPException

from control_plane.app.inmemory import (
    InMemoryMemberRepository,
    InMemoryWorkspaceRepository,
)
from control_plane.app.security.workspace_authz import require_workspace_membership


class _FakeDeps:
    """Minimal deps container for authz tests."""

    def __init__(self):
        self.workspace_repo = InMemoryWorkspaceRepository()
        self.member_repo = InMemoryMemberRepository()


@pytest.fixture()
def deps():
    return _FakeDeps()


async def _seed(deps: _FakeDeps, workspace_id: str, user_id: str, status: str = "active"):
    await deps.workspace_repo.create({
        "id": workspace_id,
        "name": "Test Workspace",
        "owner_id": user_id,
        "app_id": "boring-ui",
    })
    await deps.member_repo.add_member(workspace_id, {
        "user_id": user_id,
        "email": "test@example.com",
        "role": "admin",
        "status": status,
    })


# ── Test: happy path ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_active_member_allowed(deps):
    await _seed(deps, "ws_1", "user-1")
    membership = await require_workspace_membership("ws_1", "user-1", deps)
    assert membership["user_id"] == "user-1"
    assert membership["role"] == "admin"


# ── Test: 401 without user ID ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_401_without_user_id(deps):
    await _seed(deps, "ws_1", "user-1")
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_membership("ws_1", None, deps)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_401_with_empty_user_id(deps):
    await _seed(deps, "ws_1", "user-1")
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_membership("ws_1", "", deps)
    assert exc_info.value.status_code == 401


# ── Test: 404 workspace not found ─────────────────────────────────────


@pytest.mark.asyncio
async def test_404_workspace_not_found(deps):
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_membership("ws_nonexistent", "user-1", deps)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "WORKSPACE_NOT_FOUND"


# ── Test: 403 not a member ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_403_non_member(deps):
    await _seed(deps, "ws_1", "user-1")
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_membership("ws_1", "user-other", deps)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "FORBIDDEN"


# ── Test: 403 removed member ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_403_removed_member(deps):
    await _seed(deps, "ws_1", "user-1", status="removed")
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_membership("ws_1", "user-1", deps)
    assert exc_info.value.status_code == 403


# ── Test: 403 pending member ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_403_pending_member(deps):
    await _seed(deps, "ws_1", "user-1", status="pending")
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_membership("ws_1", "user-1", deps)
    assert exc_info.value.status_code == 403


# ── Test: cross-tenant isolation ──────────────────────────────────────


@pytest.mark.asyncio
async def test_user_a_cannot_access_user_b_workspace(deps):
    """User A cannot access User B's workspace even with valid auth."""
    await _seed(deps, "ws_a", "user-a")
    # user-b is not a member of ws_a
    await deps.workspace_repo.create({
        "id": "ws_b",
        "name": "B Workspace",
        "owner_id": "user-b",
        "app_id": "boring-ui",
    })
    await deps.member_repo.add_member("ws_b", {
        "user_id": "user-b",
        "email": "b@example.com",
        "role": "admin",
        "status": "active",
    })

    # user-b tries to access ws_a
    with pytest.raises(HTTPException) as exc_info:
        await require_workspace_membership("ws_a", "user-b", deps)
    assert exc_info.value.status_code == 403
