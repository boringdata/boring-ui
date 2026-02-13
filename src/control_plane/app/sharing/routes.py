"""Share-link create/revoke/list API endpoints.

Bead: bd-223o.12.2 (F2)

Implements share-link management endpoints from Feature 3 design doc
section 11:

  POST   /w/{workspace_id}/api/v1/shares          → create share link
  GET    /w/{workspace_id}/api/v1/shares          → list workspace shares
  DELETE /w/{workspace_id}/api/v1/shares/{share_id} → revoke share link

Auth contract:
  - All endpoints require authenticated session (AuthIdentity).
  - Caller must be an active member of the workspace.
  - Non-members receive 403 forbidden.

Token security:
  - Plaintext token is returned exactly once in the create response.
  - Only the SHA-256 hash is persisted; plaintext never stored.

Default expiry:
  - 72 hours (configurable via ``expires_in_hours``).
  - Minimum 1 hour, maximum 720 hours (30 days).

This module provides:
  ``create_share_router`` — FastAPI router factory with injected deps.
"""

from __future__ import annotations

import posixpath
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from control_plane.app.security.auth_guard import get_auth_identity
from control_plane.app.security.token_verify import AuthIdentity

from .model import (
    DEFAULT_EXPIRY_HOURS,
    ShareLink,
    ShareLinkRepository,
    generate_share_token,
    hash_token,
)

# Re-use membership checker protocol from agent sessions.
from control_plane.app.agent.sessions import MembershipChecker


# ── Path validation ──────────────────────────────────────────────────

MIN_EXPIRY_HOURS = 1
MAX_EXPIRY_HOURS = 720  # 30 days.

VALID_ACCESS_MODES = frozenset({'read', 'write'})


def normalize_share_path(path: str) -> str | None:
    """Normalize a workspace-relative path for exact-path sharing.

    Returns the normalized path or None if it contains traversal.
    Paths must be absolute workspace-relative (start with ``/``).

    Traversal detection: if the raw path contains ``..`` segments at all,
    it's rejected outright. This prevents both obvious escapes
    (``/docs/../../../etc/passwd``) and subtle ones.
    """
    if not path or not path.startswith('/'):
        return None

    # Reject any path containing parent-directory references.
    if '/..' in path or path == '/..':
        return None

    normalized = posixpath.normpath(path)

    # Ensure it still starts with /.
    if not normalized.startswith('/'):
        return None

    return normalized


# ── Request schemas ──────────────────────────────────────────────────


class CreateShareRequest(BaseModel):
    """Request body for share link creation."""

    path: str = Field(..., min_length=1, description='Workspace-relative path')
    access: str = Field(default='read', description='Access mode: read or write')
    expires_in_hours: int = Field(
        default=DEFAULT_EXPIRY_HOURS,
        ge=MIN_EXPIRY_HOURS,
        le=MAX_EXPIRY_HOURS,
        description='Link expiry in hours',
    )


# ── Shared helpers ───────────────────────────────────────────────────


async def _check_membership(
    membership: MembershipChecker,
    workspace_id: str,
    user_id: str,
) -> JSONResponse | None:
    """Return 403 JSONResponse if user is not an active member, else None."""
    if not await membership.is_active_member(workspace_id, user_id):
        return JSONResponse(
            status_code=403,
            content={
                'error': 'forbidden',
                'detail': 'Not an active member of this workspace.',
            },
        )
    return None


# ── Route factory ────────────────────────────────────────────────────


def create_share_router(
    share_repo: ShareLinkRepository,
    membership: MembershipChecker,
) -> APIRouter:
    """Create share-link management router with injected dependencies.

    Args:
        share_repo: Share link repository.
        membership: Membership checker for authorization.

    Returns:
        FastAPI router with share lifecycle routes.
    """
    router = APIRouter(tags=['share-links'])

    @router.post(
        '/w/{workspace_id}/api/v1/shares',
        status_code=201,
    )
    async def create_share(
        workspace_id: str,
        body: CreateShareRequest,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Create a share link for a workspace file.

        Requires active workspace membership.
        Returns 201 with share metadata and the plaintext token (once only).
        """
        deny = await _check_membership(membership, workspace_id, identity.user_id)
        if deny:
            return deny

        # Validate access mode.
        if body.access not in VALID_ACCESS_MODES:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'invalid_access',
                    'detail': f'Access must be one of: {sorted(VALID_ACCESS_MODES)}',
                },
            )

        # Normalize and validate path.
        normalized = normalize_share_path(body.path)
        if normalized is None:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'invalid_path',
                    'detail': 'Path must be absolute workspace-relative and free of traversal.',
                },
            )

        # Generate token and compute hash.
        plaintext_token = generate_share_token()
        token_h = hash_token(plaintext_token)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=body.expires_in_hours)

        link = ShareLink(
            id=0,  # Assigned by repository.
            workspace_id=workspace_id,
            path=normalized,
            token_hash=token_h,
            access=body.access,
            created_by=identity.user_id,
            expires_at=expires_at,
            created_at=now,
        )
        link = await share_repo.create(link)

        return {
            'share_id': link.id,
            'token': plaintext_token,
            'workspace_id': link.workspace_id,
            'path': link.path,
            'access': link.access,
            'expires_at': link.expires_at.isoformat(),
            'created_by': link.created_by,
        }

    @router.get('/w/{workspace_id}/api/v1/shares')
    async def list_shares(
        workspace_id: str,
        include_revoked: bool = False,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """List share links for a workspace."""
        deny = await _check_membership(membership, workspace_id, identity.user_id)
        if deny:
            return deny

        links = await share_repo.list_for_workspace(
            workspace_id, include_revoked=include_revoked,
        )
        return {
            'shares': [
                {
                    'share_id': l.id,
                    'path': l.path,
                    'access': l.access,
                    'created_by': l.created_by,
                    'expires_at': l.expires_at.isoformat(),
                    'is_active': l.is_active,
                    'is_expired': l.is_expired,
                    'is_revoked': l.is_revoked,
                }
                for l in links
            ],
        }

    @router.delete(
        '/w/{workspace_id}/api/v1/shares/{share_id}',
    )
    async def revoke_share(
        workspace_id: str,
        share_id: int,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Revoke a share link. Idempotent.

        Returns the revoked share metadata, or 404 if not found.
        """
        deny = await _check_membership(membership, workspace_id, identity.user_id)
        if deny:
            return deny

        link = await share_repo.revoke(share_id, workspace_id)
        if link is None:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'share_not_found',
                    'detail': f'Share {share_id} not found in workspace.',
                },
            )

        return {
            'share_id': link.id,
            'path': link.path,
            'revoked_at': link.revoked_at.isoformat() if link.revoked_at else None,
            'is_active': link.is_active,
        }

    return router
