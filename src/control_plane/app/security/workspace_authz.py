"""Workspace authorization helpers.

Bead: bd-1joj.12 (AUTHZ0)

Shared authz dependency for workspace-scoped endpoints. Enforces tenant
isolation by requiring active membership before allowing access.

User identity is resolved from X-User-ID header (local dev / testing).
AUTH0 will replace this with Supabase JWT decoding.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def get_request_user_id(request: Request) -> str | None:
    """Extract user identity from request.

    For local dev/testing, reads X-User-ID header.
    AUTH0 will replace this with Supabase JWT decoding.
    """
    return request.headers.get("x-user-id")


async def require_workspace_membership(
    workspace_id: str,
    user_id: str | None,
    deps: Any,
) -> dict[str, Any]:
    """Verify user has active membership in workspace.

    Returns the membership dict (with role) on success.

    Raises:
        HTTPException(401): If user_id is None (no auth).
        HTTPException(404): If workspace does not exist.
        HTTPException(403): If user is not an active member.
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "User identity required"},
        )

    workspace = await deps.workspace_repo.get(workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "WORKSPACE_NOT_FOUND", "message": f"Workspace {workspace_id} not found"},
        )

    membership = await deps.member_repo.get_membership(workspace_id, user_id)
    if membership is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Not an active member of this workspace"},
        )

    # InMemory impl may not filter by status — double-check here
    status = membership.get("status")
    if status is not None and status != "active":
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Membership is not active"},
        )

    return membership
