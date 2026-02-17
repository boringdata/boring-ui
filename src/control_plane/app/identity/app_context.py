"""App context validation for workspace-scoped routes.

Bead: bd-223o.8.3 (I3)

Prevents cross-app data bleed by validating that the request's resolved
``app_id`` (from host mapping) matches the workspace's ``app_id``.

Design doc section 10, point 8:
  - Resolved host → app_id must match workspace.app_id
  - Mismatch → ``400 app_context_mismatch``

This module provides:
  1. A pure validation function (``validate_app_context``)
  2. A Starlette middleware (``AppContextMiddleware``) that performs
     the check on workspace-scoped routes automatically.

The middleware reads:
  - ``request.state.app_id``: Set by upstream identity resolution middleware.
  - ``request.state.workspace_app_id``: Set by workspace resolution middleware
    (only present on workspace-scoped routes).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class AppContextMismatch(Exception):
    """Raised when resolved app_id does not match workspace app_id."""

    def __init__(self, resolved: str, workspace: str) -> None:
        self.resolved_app_id = resolved
        self.workspace_app_id = workspace
        super().__init__(
            f'Resolved app_id {resolved!r} does not match '
            f'workspace app_id {workspace!r}'
        )


def validate_app_context(
    resolved_app_id: str | None,
    workspace_app_id: str | None,
) -> None:
    """Validate that the resolved app identity matches the workspace.

    Args:
        resolved_app_id: The app_id resolved from the request host.
        workspace_app_id: The app_id stored on the workspace record.

    Raises:
        AppContextMismatch: If both are present and they differ.

    No-op when either value is ``None`` (non-workspace routes or
    workspace not yet resolved).
    """
    if resolved_app_id is None or workspace_app_id is None:
        return

    if resolved_app_id != workspace_app_id:
        raise AppContextMismatch(resolved_app_id, workspace_app_id)


class AppContextMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing app_id consistency on workspace-scoped routes.

    Reads ``request.state.app_id`` and ``request.state.workspace_app_id``.
    If both are present and they differ, returns ``400 app_context_mismatch``.

    Non-workspace routes (where ``workspace_app_id`` is not set) pass through.
    """

    async def dispatch(
        self, request: Request, call_next
    ) -> Response:
        resolved = getattr(request.state, 'app_id', None)
        workspace = getattr(request.state, 'workspace_app_id', None)

        try:
            validate_app_context(resolved, workspace)
        except AppContextMismatch as exc:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'app_context_mismatch',
                    'resolved_app_id': exc.resolved_app_id,
                    'workspace_app_id': exc.workspace_app_id,
                },
            )

        return await call_next(request)
