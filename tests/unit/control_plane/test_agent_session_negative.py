"""Non-member and missing-session negative tests.

Bead: bd-223o.13.2.1 (G2a)

Validates:
  - Non-members consistently get 403 across all endpoints
  - Missing sessions consistently get 404 across all endpoints
  - Cross-workspace session access returns 404 (not 403)
  - Stopped session returns 409 for active-required endpoints
  - Membership gating checked before session lookup
  - Wrong workspace session ID returns 404 not 200
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from control_plane.app.agent.sessions import (
    InMemoryAgentSessionRepository,
    InMemoryMembershipChecker,
    create_agent_session_router,
)
from control_plane.app.security.token_verify import AuthIdentity


def _make_app(members=None, user_id='user_1'):
    app = FastAPI()
    repo = InMemoryAgentSessionRepository()
    checker = InMemoryMembershipChecker(members or set())
    router = create_agent_session_router(repo, checker)
    app.include_router(router)

    @app.middleware('http')
    async def fake_auth(request: Request, call_next):
        request.state.auth_identity = AuthIdentity(
            user_id=user_id, email='u@test.com', role='authenticated',
        )
        return await call_next(request)

    app.state.session_repo = repo
    app.state.membership = checker
    return app


# =====================================================================
# 1. Non-member 403 across all endpoints
# =====================================================================


class TestNonMember403:
    """Non-members must get 403 on every workspace-scoped endpoint."""

    @pytest.fixture
    def app(self):
        return _make_app(members=set())

    @pytest.mark.asyncio
    async def test_create_403(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 403
            assert r.json()['error'] == 'forbidden'

    @pytest.mark.asyncio
    async def test_list_403(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_stream_403(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/w/ws_1/api/v1/agent/sessions/sess_fake/stream')
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_input_403(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post(
                '/w/ws_1/api/v1/agent/sessions/sess_fake/input',
                json={'content': 'test'},
            )
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_stop_403(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions/sess_fake/stop')
            assert r.status_code == 403


# =====================================================================
# 2. Missing session 404 across lifecycle endpoints
# =====================================================================


class TestMissingSession404:
    """Missing session IDs must return 404 on lifecycle endpoints."""

    @pytest.fixture
    def app(self):
        return _make_app(members={('ws_1', 'user_1')})

    @pytest.mark.asyncio
    async def test_stream_missing_session_404(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/w/ws_1/api/v1/agent/sessions/sess_nonexistent/stream')
            assert r.status_code == 404
            assert r.json()['error'] == 'session_not_found'

    @pytest.mark.asyncio
    async def test_input_missing_session_404(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post(
                '/w/ws_1/api/v1/agent/sessions/sess_nonexistent/input',
                json={'content': 'test'},
            )
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_missing_session_404(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions/sess_nonexistent/stop')
            assert r.status_code == 404


# =====================================================================
# 3. Cross-workspace session access
# =====================================================================


class TestCrossWorkspaceAccess:
    """Sessions are workspace-scoped; cross-workspace access returns 404."""

    @pytest.mark.asyncio
    async def test_session_in_ws1_not_found_via_ws2(self):
        """Session created in ws_1, accessed via ws_2 path → 404."""
        app = _make_app(members={('ws_1', 'user_1'), ('ws_2', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']

            # Try to stream via ws_2 — should be 404.
            r = await c.get(f'/w/ws_2/api/v1/agent/sessions/{sid}/stream')
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_cross_workspace_404(self):
        app = _make_app(members={('ws_1', 'user_1'), ('ws_2', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.post(f'/w/ws_2/api/v1/agent/sessions/{sid}/stop')
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_input_cross_workspace_404(self):
        app = _make_app(members={('ws_1', 'user_1'), ('ws_2', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.post(
                f'/w/ws_2/api/v1/agent/sessions/{sid}/input',
                json={'content': 'cross-ws'},
            )
            assert r.status_code == 404


# =====================================================================
# 4. Stopped session 409 on active-required endpoints
# =====================================================================


class TestStoppedSession409:
    """Stopped sessions return 409 for stream and input."""

    @pytest.mark.asyncio
    async def test_stream_stopped_409(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            r = await c.get(f'/w/ws_1/api/v1/agent/sessions/{sid}/stream')
            assert r.status_code == 409
            assert r.json()['error'] == 'session_stopped'

    @pytest.mark.asyncio
    async def test_input_stopped_409(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            r = await c.post(
                f'/w/ws_1/api/v1/agent/sessions/{sid}/input',
                json={'content': 'too late'},
            )
            assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_stop_already_stopped_is_idempotent(self):
        """Stopping an already-stopped session is idempotent (not 409)."""
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r1 = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            assert r1.status_code == 200
            r2 = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            assert r2.status_code == 200


# =====================================================================
# 5. Membership checked before session lookup
# =====================================================================


class TestMembershipBeforeSession:
    """403 takes precedence over 404 — membership gate runs first."""

    @pytest.mark.asyncio
    async def test_non_member_with_valid_session_gets_403(self):
        """Even if session exists, non-member gets 403 not 200."""
        # Create session as member, then test as non-member.
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']

        # Now remove membership and try to access.
        app.state.membership._members.clear()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(f'/w/ws_1/api/v1/agent/sessions/{sid}/stream')
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_non_member_with_fake_session_gets_403_not_404(self):
        """Non-member should get 403, not 404, even for fake session IDs."""
        app = _make_app(members=set())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions/sess_fake/stop')
            assert r.status_code == 403
