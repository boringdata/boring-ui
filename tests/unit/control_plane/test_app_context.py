"""App context mismatch enforcement tests.

Bead: bd-223o.8.3 (I3)

Tests:
  - validate_app_context: matching, mismatching, None values
  - AppContextMiddleware: mismatch → 400, match → pass, no workspace → pass
  - AppContextMismatch exception carries both app_ids
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from control_plane.app.identity.app_context import (
    AppContextMiddleware,
    AppContextMismatch,
    validate_app_context,
)

# =====================================================================
# Pure validation function
# =====================================================================


class TestValidateAppContext:
    def test_matching_app_ids_pass(self):
        validate_app_context('boring-ui', 'boring-ui')  # Should not raise.

    def test_mismatching_app_ids_raise(self):
        with pytest.raises(AppContextMismatch):
            validate_app_context('boring-ui', 'acme-app')

    def test_none_resolved_passes(self):
        validate_app_context(None, 'boring-ui')  # No-op.

    def test_none_workspace_passes(self):
        validate_app_context('boring-ui', None)  # No-op.

    def test_both_none_passes(self):
        validate_app_context(None, None)  # No-op.


class TestAppContextMismatchException:
    def test_carries_both_app_ids(self):
        exc = AppContextMismatch('resolved-app', 'workspace-app')
        assert exc.resolved_app_id == 'resolved-app'
        assert exc.workspace_app_id == 'workspace-app'

    def test_message_includes_both(self):
        exc = AppContextMismatch('a', 'b')
        assert 'a' in str(exc)
        assert 'b' in str(exc)


# =====================================================================
# Middleware integration
# =====================================================================


class _FakeContextMiddleware(BaseHTTPMiddleware):
    """Sets app_id and workspace_app_id on request.state for testing."""

    def __init__(self, app, app_id=None, workspace_app_id=None):
        super().__init__(app)
        self._app_id = app_id
        self._workspace_app_id = workspace_app_id

    async def dispatch(self, request, call_next):
        if self._app_id is not None:
            request.state.app_id = self._app_id
        if self._workspace_app_id is not None:
            request.state.workspace_app_id = self._workspace_app_id
        return await call_next(request)


def _build_app(app_id=None, workspace_app_id=None) -> FastAPI:
    app = FastAPI()

    # Inner: AppContextMiddleware. Outer: FakeContextMiddleware.
    app.add_middleware(AppContextMiddleware)
    app.add_middleware(
        _FakeContextMiddleware,
        app_id=app_id,
        workspace_app_id=workspace_app_id,
    )

    @app.get('/w/{ws_id}/api/v1/files')
    async def list_files(request: Request, ws_id: str):
        return {'workspace_id': ws_id}

    @app.get('/api/v1/me')
    async def me(request: Request):
        return {'user': 'test'}

    return app


class TestAppContextMiddlewareMismatch:
    @pytest.mark.asyncio
    async def test_mismatch_returns_400(self):
        app = _build_app(app_id='boring-ui', workspace_app_id='acme-app')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/w/ws_123/api/v1/files')
            assert resp.status_code == 400
            body = resp.json()
            assert body['error'] == 'app_context_mismatch'
            assert body['resolved_app_id'] == 'boring-ui'
            assert body['workspace_app_id'] == 'acme-app'

    @pytest.mark.asyncio
    async def test_match_passes_through(self):
        app = _build_app(app_id='boring-ui', workspace_app_id='boring-ui')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/w/ws_123/api/v1/files')
            assert resp.status_code == 200
            assert resp.json()['workspace_id'] == 'ws_123'


class TestAppContextMiddlewareNoWorkspace:
    @pytest.mark.asyncio
    async def test_non_workspace_route_passes(self):
        """Routes without workspace_app_id skip validation."""
        app = _build_app(app_id='boring-ui')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/api/v1/me')
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_no_app_id_resolved_passes(self):
        """If app_id is not resolved yet, skip validation."""
        app = _build_app(workspace_app_id='boring-ui')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/w/ws_123/api/v1/files')
            assert resp.status_code == 200
