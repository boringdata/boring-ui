"""Negative tests for workspace context conflict and mismatch.

Bead: bd-223o.11.2.1 (E2a)

Validates:
  - All pairwise conflict combinations produce WorkspaceContextMismatch
  - Exception carries correct source mapping
  - Deterministic 400 response structure via middleware integration
  - Edge cases: empty strings, case sensitivity, whitespace
  - WorkspaceContext immutability
  - Mismatch message format stability
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from control_plane.app.routing.context import (
    WorkspaceContext,
    WorkspaceContextMismatch,
    resolve_workspace_context,
)


# ── Helpers ──────────────────────────────────────────────────────────


class _WorkspaceContextMiddleware(BaseHTTPMiddleware):
    """Simulate workspace context resolution in middleware.

    Reads workspace_id from path, header, and session (cookie/default),
    calls resolve_workspace_context, and returns 400 on mismatch.
    """

    def __init__(self, app, session_workspace_id=None):
        super().__init__(app)
        self._session_ws = session_workspace_id

    @staticmethod
    def _extract_path_workspace_id(path: str) -> str | None:
        """Extract workspace_id from /w/{workspace_id}/... paths."""
        if path.startswith('/w/'):
            rest = path[3:]
            slash = rest.find('/')
            if slash > 0:
                return rest[:slash]
            elif rest:
                return rest
        return None

    async def dispatch(self, request, call_next):
        path_ws = self._extract_path_workspace_id(request.url.path)
        header_ws = request.headers.get('x-workspace-id')
        session_ws = self._session_ws

        try:
            ctx = resolve_workspace_context(
                path_workspace_id=path_ws,
                header_workspace_id=header_ws,
                session_workspace_id=session_ws,
            )
        except WorkspaceContextMismatch as exc:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'workspace_context_mismatch',
                    'sources': exc.sources,
                },
            )

        if ctx is not None:
            request.state.workspace_context = ctx
        return await call_next(request)


def _build_test_app(session_workspace_id=None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        _WorkspaceContextMiddleware,
        session_workspace_id=session_workspace_id,
    )

    @app.get('/w/{workspace_id}/api/v1/files')
    async def workspace_files(workspace_id: str):
        return {'workspace_id': workspace_id}

    @app.get('/api/v1/me')
    async def me():
        return {'user': 'test'}

    return app


# =====================================================================
# 1. Pairwise conflict combinations (pure function)
# =====================================================================


class TestPairwiseConflicts:

    def test_path_vs_header(self):
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                path_workspace_id='ws_A',
                header_workspace_id='ws_B',
            )
        assert exc_info.value.sources == {'path': 'ws_A', 'header': 'ws_B'}

    def test_path_vs_session(self):
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                path_workspace_id='ws_A',
                session_workspace_id='ws_C',
            )
        assert exc_info.value.sources == {'path': 'ws_A', 'session': 'ws_C'}

    def test_header_vs_session(self):
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                header_workspace_id='ws_B',
                session_workspace_id='ws_C',
            )
        assert exc_info.value.sources == {'header': 'ws_B', 'session': 'ws_C'}

    def test_all_three_different(self):
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                path_workspace_id='ws_1',
                header_workspace_id='ws_2',
                session_workspace_id='ws_3',
            )
        assert len(exc_info.value.sources) == 3

    def test_path_header_agree_session_disagrees(self):
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                path_workspace_id='ws_same',
                header_workspace_id='ws_same',
                session_workspace_id='ws_other',
            )
        sources = exc_info.value.sources
        assert sources['path'] == 'ws_same'
        assert sources['session'] == 'ws_other'

    def test_path_session_agree_header_disagrees(self):
        with pytest.raises(WorkspaceContextMismatch) as exc_info:
            resolve_workspace_context(
                path_workspace_id='ws_same',
                header_workspace_id='ws_rogue',
                session_workspace_id='ws_same',
            )
        assert exc_info.value.sources['header'] == 'ws_rogue'


# =====================================================================
# 2. Edge cases: empty strings, case, whitespace
# =====================================================================


class TestEdgeCases:

    def test_empty_string_vs_nonempty_mismatch(self):
        """Empty string is a valid value and should mismatch."""
        with pytest.raises(WorkspaceContextMismatch):
            resolve_workspace_context(
                path_workspace_id='',
                header_workspace_id='ws_1',
            )

    def test_case_sensitive_mismatch(self):
        """ws_ABC != ws_abc — IDs are case-sensitive."""
        with pytest.raises(WorkspaceContextMismatch):
            resolve_workspace_context(
                path_workspace_id='ws_ABC',
                header_workspace_id='ws_abc',
            )

    def test_whitespace_difference_mismatch(self):
        """Leading/trailing whitespace differences are mismatches."""
        with pytest.raises(WorkspaceContextMismatch):
            resolve_workspace_context(
                path_workspace_id='ws_1',
                header_workspace_id=' ws_1',
            )

    def test_empty_strings_agree(self):
        """Two empty strings should agree."""
        ctx = resolve_workspace_context(
            path_workspace_id='',
            header_workspace_id='',
        )
        assert ctx is not None
        assert ctx.workspace_id == ''
        assert ctx.source == 'path'


# =====================================================================
# 3. Exception structure and message
# =====================================================================


class TestExceptionStructure:

    def test_sources_dict_is_correct(self):
        try:
            resolve_workspace_context(
                path_workspace_id='a',
                header_workspace_id='b',
                session_workspace_id='c',
            )
        except WorkspaceContextMismatch as exc:
            assert exc.sources == {'path': 'a', 'header': 'b', 'session': 'c'}
        else:
            pytest.fail('Expected WorkspaceContextMismatch')

    def test_message_contains_all_sources(self):
        try:
            resolve_workspace_context(
                path_workspace_id='alpha',
                header_workspace_id='beta',
            )
        except WorkspaceContextMismatch as exc:
            msg = str(exc)
            assert 'workspace_context_mismatch' in msg
            assert 'alpha' in msg
            assert 'beta' in msg
        else:
            pytest.fail('Expected WorkspaceContextMismatch')

    def test_exception_inherits_from_exception(self):
        exc = WorkspaceContextMismatch({'path': 'a', 'header': 'b'})
        assert isinstance(exc, Exception)

    def test_sources_keys_are_sorted_in_message(self):
        """Message format: sources sorted alphabetically."""
        exc = WorkspaceContextMismatch({'session': 's', 'header': 'h', 'path': 'p'})
        msg = str(exc)
        # Verify sorted order: header, path, session.
        h_pos = msg.index('header=')
        p_pos = msg.index('path=')
        s_pos = msg.index('session=')
        assert h_pos < p_pos < s_pos


# =====================================================================
# 4. Middleware integration — deterministic 400 response
# =====================================================================


class TestMiddlewareConflictResponse:

    @pytest.mark.asyncio
    async def test_header_vs_path_returns_400(self):
        """When X-Workspace-ID header conflicts with path, return 400."""
        app = _build_test_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get(
                '/w/ws_from_path/api/v1/files',
                headers={'x-workspace-id': 'ws_from_header'},
            )
            assert r.status_code == 400
            body = r.json()
            assert body['error'] == 'workspace_context_mismatch'
            assert body['sources']['path'] == 'ws_from_path'
            assert body['sources']['header'] == 'ws_from_header'

    @pytest.mark.asyncio
    async def test_session_vs_path_returns_400(self):
        """When session workspace conflicts with path, return 400."""
        app = _build_test_app(session_workspace_id='ws_session')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get('/w/ws_path/api/v1/files')
            assert r.status_code == 400
            body = r.json()
            assert body['error'] == 'workspace_context_mismatch'

    @pytest.mark.asyncio
    async def test_matching_header_and_path_passes(self):
        """When header agrees with path, no conflict."""
        app = _build_test_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get(
                '/w/ws_1/api/v1/files',
                headers={'x-workspace-id': 'ws_1'},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_all_three_agree_passes(self):
        """When all sources agree, request passes."""
        app = _build_test_app(session_workspace_id='ws_1')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get(
                '/w/ws_1/api/v1/files',
                headers={'x-workspace-id': 'ws_1'},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_no_workspace_route_unaffected(self):
        """Non-workspace routes should not be affected."""
        app = _build_test_app(session_workspace_id='ws_session')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get('/api/v1/me')
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_error_payload_keys_are_stable(self):
        """400 response must have exactly 'error' and 'sources'."""
        app = _build_test_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get(
                '/w/ws_path/api/v1/files',
                headers={'x-workspace-id': 'ws_header'},
            )
            assert set(r.json().keys()) == {'error', 'sources'}


# =====================================================================
# 5. WorkspaceContext immutability
# =====================================================================


class TestWorkspaceContextImmutability:

    def test_frozen(self):
        ctx = WorkspaceContext(workspace_id='ws_1', source='path')
        with pytest.raises(AttributeError):
            ctx.workspace_id = 'ws_2'

    def test_uses_slots(self):
        ctx = WorkspaceContext(workspace_id='ws_1', source='path')
        assert hasattr(ctx, '__slots__')
