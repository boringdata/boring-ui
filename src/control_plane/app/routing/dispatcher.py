"""Route dispatch middleware for the control plane.

Intercepts every request, resolves the owning plane (control vs workspace),
extracts workspace context, and annotates the request state so downstream
handlers or proxy logic can act on the decision.

Also handles X-Request-ID generation/propagation per Feature 3 design doc
section 18.4.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .context import WorkspaceContext, WorkspaceContextMismatch, resolve_workspace_context
from .ownership import Plane, RouteMatch, resolve_owner


# Header constants.
REQUEST_ID_HEADER = 'X-Request-ID'
WORKSPACE_ID_HEADER = 'X-Workspace-ID'
SESSION_ID_HEADER = 'X-Session-ID'


class RouteDispatchMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that resolves route ownership and workspace context.

    On each request the middleware:

    1. Generates or accepts ``X-Request-ID``.
    2. Matches the path against the route ownership table.
    3. Resolves workspace context (path > header > session).
    4. Stores resolution results on ``request.state`` for downstream use.
    5. Returns ``400 workspace_context_mismatch`` on conflicts.

    Request state attributes set:

    - ``request.state.request_id`` — the resolved request ID string.
    - ``request.state.route_match`` — ``RouteMatch | None``.
    - ``request.state.workspace_ctx`` — ``WorkspaceContext | None``.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # 1. X-Request-ID: accept from caller or generate.
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        # 2. Route ownership resolution.
        path = request.url.path
        route_match: RouteMatch | None = resolve_owner(path)
        request.state.route_match = route_match

        # 3. Workspace context resolution.
        path_workspace_id = route_match.workspace_id if route_match else None
        header_workspace_id = request.headers.get(WORKSPACE_ID_HEADER)
        # Session workspace is resolved by auth middleware upstream;
        # it should be placed on request.state.session_workspace_id
        # before this middleware runs.  Default to None.
        session_workspace_id = getattr(request.state, 'session_workspace_id', None)

        try:
            workspace_ctx = resolve_workspace_context(
                path_workspace_id=path_workspace_id,
                header_workspace_id=header_workspace_id,
                session_workspace_id=session_workspace_id,
            )
        except WorkspaceContextMismatch as exc:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'workspace_context_mismatch',
                    'detail': str(exc),
                    'sources': exc.sources,
                    'request_id': request_id,
                },
                headers={REQUEST_ID_HEADER: request_id},
            )

        request.state.workspace_ctx = workspace_ctx

        # 4. Workspace-plane routes require a resolved workspace_id.
        if route_match and route_match.entry.plane == Plane.WORKSPACE and workspace_ctx is None:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'missing_workspace_context',
                    'detail': 'Workspace-plane route requires a workspace_id.',
                    'request_id': request_id,
                },
                headers={REQUEST_ID_HEADER: request_id},
            )

        # 5. Forward to next handler.
        response = await call_next(request)

        # 6. Propagate X-Request-ID on response.
        response.headers[REQUEST_ID_HEADER] = request_id

        return response
