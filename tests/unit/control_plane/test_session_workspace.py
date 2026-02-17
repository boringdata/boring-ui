"""Tests for user session active-workspace tracking endpoint.

Bead: bd-223o.14.2 (H2)

Validates:
  - PUT sets the active workspace for the authenticated user.
  - GET retrieves the active workspace.
  - GET returns 404 when no active workspace is set.
  - PUT overwrites previous selection.
  - Different users have independent active workspace selections.
  - PUT requires non-empty workspace_id.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from control_plane.app.routes.session import (
    InMemorySessionRepository,
    create_session_router,
)
from control_plane.app.security.token_verify import AuthIdentity


# ── Test app ──────────────────────────────────────────────────────────


def _make_app(user_id: str = 'user_1') -> tuple[FastAPI, InMemorySessionRepository]:
    app = FastAPI()
    repo = InMemorySessionRepository()
    router = create_session_router(repo)
    app.include_router(router)

    @app.middleware('http')
    async def fake_auth(request: Request, call_next):
        request.state.auth_identity = AuthIdentity(
            user_id=user_id, email='u@t.com', role='authenticated',
        )
        return await call_next(request)

    return app, repo


def _make_multiuser_app() -> tuple[FastAPI, InMemorySessionRepository]:
    """App that reads user_id from X-Test-User header."""
    app = FastAPI()
    repo = InMemorySessionRepository()
    router = create_session_router(repo)
    app.include_router(router)

    @app.middleware('http')
    async def fake_auth(request: Request, call_next):
        user_id = request.headers.get('X-Test-User', 'user_1')
        request.state.auth_identity = AuthIdentity(
            user_id=user_id, email=f'{user_id}@t.com', role='authenticated',
        )
        return await call_next(request)

    return app, repo


# =====================================================================
# GET — no active workspace
# =====================================================================


class TestGetActiveWorkspace:
    @pytest.mark.asyncio
    async def test_get_returns_404_when_unset(self):
        app, repo = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/api/v1/session/active-workspace')
            assert r.status_code == 404
            assert r.json()['error'] == 'no_active_workspace'


# =====================================================================
# PUT — set active workspace
# =====================================================================


class TestSetActiveWorkspace:
    @pytest.mark.asyncio
    async def test_set_returns_workspace_id(self):
        app, repo = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                '/api/v1/session/active-workspace',
                json={'workspace_id': 'ws_abc123'},
            )
            assert r.status_code == 200
            assert r.json()['active_workspace_id'] == 'ws_abc123'

    @pytest.mark.asyncio
    async def test_set_then_get(self):
        app, repo = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await c.put(
                '/api/v1/session/active-workspace',
                json={'workspace_id': 'ws_abc123'},
            )
            r = await c.get('/api/v1/session/active-workspace')
            assert r.status_code == 200
            assert r.json()['active_workspace_id'] == 'ws_abc123'

    @pytest.mark.asyncio
    async def test_overwrite_active_workspace(self):
        app, repo = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await c.put(
                '/api/v1/session/active-workspace',
                json={'workspace_id': 'ws_first'},
            )
            await c.put(
                '/api/v1/session/active-workspace',
                json={'workspace_id': 'ws_second'},
            )
            r = await c.get('/api/v1/session/active-workspace')
            assert r.json()['active_workspace_id'] == 'ws_second'

    @pytest.mark.asyncio
    async def test_empty_workspace_id_rejected(self):
        app, repo = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                '/api/v1/session/active-workspace',
                json={'workspace_id': ''},
            )
            assert r.status_code == 422  # Pydantic min_length.


# =====================================================================
# Multi-user isolation
# =====================================================================


class TestMultiUserIsolation:
    @pytest.mark.asyncio
    async def test_independent_active_workspaces(self):
        app, repo = _make_multiuser_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # User 1 sets workspace A.
            await c.put(
                '/api/v1/session/active-workspace',
                json={'workspace_id': 'ws_a'},
                headers={'X-Test-User': 'user_1'},
            )
            # User 2 sets workspace B.
            await c.put(
                '/api/v1/session/active-workspace',
                json={'workspace_id': 'ws_b'},
                headers={'X-Test-User': 'user_2'},
            )

            # User 1 still has workspace A.
            r1 = await c.get(
                '/api/v1/session/active-workspace',
                headers={'X-Test-User': 'user_1'},
            )
            assert r1.json()['active_workspace_id'] == 'ws_a'

            # User 2 still has workspace B.
            r2 = await c.get(
                '/api/v1/session/active-workspace',
                headers={'X-Test-User': 'user_2'},
            )
            assert r2.json()['active_workspace_id'] == 'ws_b'

    @pytest.mark.asyncio
    async def test_user_without_active_returns_404(self):
        app, repo = _make_multiuser_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # User 1 sets workspace.
            await c.put(
                '/api/v1/session/active-workspace',
                json={'workspace_id': 'ws_a'},
                headers={'X-Test-User': 'user_1'},
            )
            # User 2 has nothing set.
            r = await c.get(
                '/api/v1/session/active-workspace',
                headers={'X-Test-User': 'user_2'},
            )
            assert r.status_code == 404
