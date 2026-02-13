"""Share-link read/write access endpoints with exact-path enforcement.

Bead: bd-223o.12.3 (F3)

Implements share access endpoints from Feature 3 design doc section 11:

  GET /api/v1/shares/{token}              → read shared file
  PUT /api/v1/shares/{token}              → write to shared file

Token resolution:
  - Token is hashed (SHA-256) and looked up in the repository.
  - Expired tokens → 410 share_expired.
  - Revoked/unknown tokens → 404 share_not_found.

Path enforcement:
  - Read: returns the file at the exact path in the share link.
  - Write: request body ``path`` must exactly match the share path.
  - Any mismatch → 403 share_scope_violation.

Access modes:
  - 'read' shares allow GET only.
  - 'write' shares allow both GET and PUT.

This module provides:
  ``create_share_access_router`` — FastAPI router factory.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .model import (
    ShareLinkExpired,
    ShareLinkNotFound,
    ShareLinkRepository,
    ShareLinkRevoked,
)
from .routes import normalize_share_path


# ── Request schemas ──────────────────────────────────────────────────


class ShareWriteRequest(BaseModel):
    """Request body for writing via a share link."""

    path: str = Field(..., min_length=1, description='File path to write')
    content: str = Field(..., description='File content to write')


# ── Route factory ────────────────────────────────────────────────────


def create_share_access_router(
    share_repo: ShareLinkRepository,
) -> APIRouter:
    """Create share access router for token-based file operations.

    Args:
        share_repo: Share link repository with resolve_token support.

    Returns:
        FastAPI router with read and write endpoints.
    """
    router = APIRouter(tags=['share-access'])

    @router.get('/api/v1/shares/{token}')
    async def read_share(token: str):
        """Read a file via share token.

        Resolves the token, validates access, and returns the file metadata.
        In production this proxies to workspace storage; here we return
        the share metadata for contract validation.

        Error responses:
          - 404: Token not found or revoked.
          - 410: Token expired.
        """
        try:
            link = await share_repo.resolve_token(token)
        except ShareLinkNotFound:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'share_not_found',
                    'detail': 'Share link not found.',
                },
            )
        except ShareLinkRevoked as exc:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'share_not_found',
                    'detail': 'Share link not found.',
                },
            )
        except ShareLinkExpired as exc:
            return JSONResponse(
                status_code=410,
                content={
                    'error': 'share_expired',
                    'detail': f'Share link expired at {exc.expired_at.isoformat()}.',
                },
            )

        return {
            'workspace_id': link.workspace_id,
            'path': link.path,
            'access': link.access,
            'content': f'<file content for {link.path}>',
        }

    @router.put('/api/v1/shares/{token}')
    async def write_share(token: str, body: ShareWriteRequest):
        """Write to a file via share token.

        Resolves the token, validates write access and exact-path match.
        In production this proxies to workspace storage; here we return
        success metadata for contract validation.

        Error responses:
          - 403: Read-only share or path mismatch.
          - 404: Token not found or revoked.
          - 410: Token expired.
        """
        try:
            link = await share_repo.resolve_token(token)
        except ShareLinkNotFound:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'share_not_found',
                    'detail': 'Share link not found.',
                },
            )
        except ShareLinkRevoked:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'share_not_found',
                    'detail': 'Share link not found.',
                },
            )
        except ShareLinkExpired as exc:
            return JSONResponse(
                status_code=410,
                content={
                    'error': 'share_expired',
                    'detail': f'Share link expired at {exc.expired_at.isoformat()}.',
                },
            )

        # Check write access.
        if link.access != 'write':
            return JSONResponse(
                status_code=403,
                content={
                    'error': 'share_scope_violation',
                    'detail': 'This share link does not allow write access.',
                },
            )

        # Normalize and validate the request path.
        normalized = normalize_share_path(body.path)
        if normalized is None:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'invalid_path',
                    'detail': 'Path must be absolute workspace-relative and free of traversal.',
                },
            )

        # Exact-path enforcement.
        if normalized != link.path:
            return JSONResponse(
                status_code=403,
                content={
                    'error': 'share_scope_violation',
                    'detail': f'Path {normalized!r} does not match share scope {link.path!r}.',
                },
            )

        return {
            'status': 'ok',
            'workspace_id': link.workspace_id,
            'path': link.path,
        }

    return router
