"""Tests for RouteDispatchMiddleware.

Validates X-Request-ID handling, workspace context mismatch HTTP responses,
and request state annotation.
"""

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from control_plane.app.routing.dispatcher import (
    REQUEST_ID_HEADER,
    WORKSPACE_ID_HEADER,
    RouteDispatchMiddleware,
)
from control_plane.app.routing.ownership import Plane


def _create_test_app() -> FastAPI:
    """Build a minimal FastAPI app with the dispatch middleware."""
    app = FastAPI()
    app.add_middleware(RouteDispatchMiddleware)

    @app.get('/api/v1/me')
    async def me(request: Request):
        return {
            'plane': request.state.route_match.entry.plane.value,
            'request_id': request.state.request_id,
        }

    @app.get('/api/v1/workspaces')
    async def workspaces(request: Request):
        return {'plane': request.state.route_match.entry.plane.value}

    @app.get('/w/{workspace_id}/api/v1/files')
    async def files(request: Request):
        return {
            'plane': request.state.route_match.entry.plane.value,
            'workspace_id': request.state.workspace_ctx.workspace_id,
            'workspace_source': request.state.workspace_ctx.source,
        }

    @app.get('/health')
    async def health(request: Request):
        return {
            'route_match': request.state.route_match,
            'request_id': request.state.request_id,
        }

    return app


@pytest.fixture
def app():
    return _create_test_app()


class TestRequestIdHandling:
    """X-Request-ID generation and propagation."""

    @pytest.mark.asyncio
    async def test_generates_request_id_when_absent(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/me')
            assert r.status_code == 200
            assert REQUEST_ID_HEADER in r.headers
            assert len(r.headers[REQUEST_ID_HEADER]) > 0

    @pytest.mark.asyncio
    async def test_preserves_caller_request_id(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/me',
                headers={REQUEST_ID_HEADER: 'req_caller_123'},
            )
            assert r.status_code == 200
            assert r.headers[REQUEST_ID_HEADER] == 'req_caller_123'
            assert r.json()['request_id'] == 'req_caller_123'


class TestControlPlaneDispatch:
    """Control plane routes are annotated correctly."""

    @pytest.mark.asyncio
    async def test_me_endpoint_resolves_to_control_plane(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/me')
            assert r.status_code == 200
            assert r.json()['plane'] == 'control'


class TestWorkspacePlaneDispatch:
    """Workspace plane routes extract workspace context."""

    @pytest.mark.asyncio
    async def test_workspace_route_extracts_id_from_path(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/w/ws_test/api/v1/files')
            assert r.status_code == 200
            data = r.json()
            assert data['plane'] == 'workspace'
            assert data['workspace_id'] == 'ws_test'
            assert data['workspace_source'] == 'path'


class TestWorkspaceContextMismatch:
    """Conflicting workspace sources return 400."""

    @pytest.mark.asyncio
    async def test_path_header_mismatch_returns_400(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/w/ws_from_path/api/v1/files',
                headers={WORKSPACE_ID_HEADER: 'ws_from_header'},
            )
            assert r.status_code == 400
            data = r.json()
            assert data['error'] == 'workspace_context_mismatch'
            assert 'sources' in data
            assert REQUEST_ID_HEADER in r.headers


class TestUnmatchedRoutes:
    """Unmatched routes pass through with None route_match."""

    @pytest.mark.asyncio
    async def test_health_has_none_route_match(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/health')
            assert r.status_code == 200
            data = r.json()
            assert data['route_match'] is None
            assert data['request_id'] is not None
