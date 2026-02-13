"""Tests for workspace-scoped agent session create endpoint.

Bead: bd-223o.13.1 (G1)

Validates:
  - Session creation with membership gate.
  - Non-member access denied with 403.
  - Session listing per workspace.
  - Idempotent stop behavior.
  - Session response payload contract.
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


# ── Test helpers ──────────────────────────────────────────────────────


def _make_app(
    members: set[tuple[str, str]] | None = None,
    user_id: str = 'user_1',
    email: str = 'user@test.com',
) -> FastAPI:
    """Build a test app with agent session routes and fake auth."""
    app = FastAPI()
    repo = InMemoryAgentSessionRepository()
    checker = InMemoryMembershipChecker(members or set())

    router = create_agent_session_router(repo, checker)
    app.include_router(router)

    # Fake auth: inject identity into request state.
    @app.middleware('http')
    async def fake_auth(request: Request, call_next):
        request.state.auth_identity = AuthIdentity(
            user_id=user_id,
            email=email,
            role='authenticated',
        )
        return await call_next(request)

    # Store refs for test manipulation.
    app.state.session_repo = repo
    app.state.membership = checker

    return app


@pytest.fixture
def member_app():
    """App where user_1 is a member of ws_1."""
    return _make_app(members={('ws_1', 'user_1')})


@pytest.fixture
def no_member_app():
    """App where user_1 is NOT a member of any workspace."""
    return _make_app(members=set())


# =====================================================================
# Session creation
# =====================================================================


class TestCreateSession:
    """POST /w/{workspace_id}/api/v1/agent/sessions."""

    @pytest.mark.asyncio
    async def test_create_returns_201(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 201

    @pytest.mark.asyncio
    async def test_create_returns_session_metadata(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            data = r.json()
            assert 'session_id' in data
            assert data['workspace_id'] == 'ws_1'
            assert data['created_by'] == 'user_1'
            assert 'created_at' in data

    @pytest.mark.asyncio
    async def test_session_id_starts_with_sess(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            assert r.json()['session_id'].startswith('sess_')

    @pytest.mark.asyncio
    async def test_non_member_gets_403(self, no_member_app):
        transport = ASGITransport(app=no_member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 403
            assert r.json()['error'] == 'forbidden'

    @pytest.mark.asyncio
    async def test_multiple_sessions_different_ids(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r1 = await c.post('/w/ws_1/api/v1/agent/sessions')
            r2 = await c.post('/w/ws_1/api/v1/agent/sessions')
            assert r1.json()['session_id'] != r2.json()['session_id']


# =====================================================================
# Session listing
# =====================================================================


class TestListSessions:
    """GET /w/{workspace_id}/api/v1/agent/sessions."""

    @pytest.mark.asyncio
    async def test_list_returns_created_sessions(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await c.post('/w/ws_1/api/v1/agent/sessions')
            await c.post('/w/ws_1/api/v1/agent/sessions')
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 200
            assert len(r.json()['sessions']) == 2

    @pytest.mark.asyncio
    async def test_list_empty_workspace(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 200
            assert r.json()['sessions'] == []

    @pytest.mark.asyncio
    async def test_list_non_member_gets_403(self, no_member_app):
        transport = ASGITransport(app=no_member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_list_shows_active_status(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            sessions = r.json()['sessions']
            assert sessions[0]['is_active'] is True


# =====================================================================
# Session stop
# =====================================================================


class TestStopSession:
    """POST /w/{workspace_id}/api/v1/agent/sessions/{session_id}/stop."""

    @pytest.mark.asyncio
    async def test_stop_returns_stopped_metadata(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            create_r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = create_r.json()['session_id']
            r = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            assert r.status_code == 200
            data = r.json()
            assert data['session_id'] == sid
            assert data['is_active'] is False
            assert 'stopped_at' in data

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            create_r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = create_r.json()['session_id']
            r1 = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            r2 = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            assert r1.json()['stopped_at'] == r2.json()['stopped_at']

    @pytest.mark.asyncio
    async def test_stop_nonexistent_session_returns_404(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions/sess_fake/stop')
            assert r.status_code == 404
            assert r.json()['error'] == 'session_not_found'

    @pytest.mark.asyncio
    async def test_stop_non_member_gets_403(self, no_member_app):
        transport = ASGITransport(app=no_member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions/sess_any/stop')
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_stop_wrong_workspace_returns_404(self, member_app):
        """Session created in ws_1 but stopped via ws_2 path."""
        # Add user as member of ws_2 too.
        member_app.state.membership.add_member('ws_2', 'user_1')
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            create_r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = create_r.json()['session_id']
            r = await c.post(f'/w/ws_2/api/v1/agent/sessions/{sid}/stop')
            assert r.status_code == 404


# =====================================================================
# Stream endpoint (G2)
# =====================================================================


class TestStreamSession:
    """GET /w/{workspace_id}/api/v1/agent/sessions/{session_id}/stream."""

    @pytest.mark.asyncio
    async def test_stream_active_session(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.get(f'/w/ws_1/api/v1/agent/sessions/{sid}/stream')
            assert r.status_code == 200
            data = r.json()
            assert data['session_id'] == sid
            assert data['stream'] == 'connected'

    @pytest.mark.asyncio
    async def test_stream_non_member_gets_403(self, no_member_app):
        transport = ASGITransport(app=no_member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/w/ws_1/api/v1/agent/sessions/sess_any/stream')
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_stream_missing_session_returns_404(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/w/ws_1/api/v1/agent/sessions/sess_nope/stream')
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_stream_stopped_session_returns_409(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            r = await c.get(f'/w/ws_1/api/v1/agent/sessions/{sid}/stream')
            assert r.status_code == 409
            assert r.json()['error'] == 'session_stopped'


# =====================================================================
# Input endpoint (G2)
# =====================================================================


class TestSendInput:
    """POST /w/{workspace_id}/api/v1/agent/sessions/{session_id}/input."""

    @pytest.mark.asyncio
    async def test_input_active_session(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.post(
                f'/w/ws_1/api/v1/agent/sessions/{sid}/input',
                json={'content': 'hello agent'},
            )
            assert r.status_code == 200
            assert r.json()['accepted'] is True

    @pytest.mark.asyncio
    async def test_input_non_member_gets_403(self, no_member_app):
        transport = ASGITransport(app=no_member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/agent/sessions/sess_any/input',
                json={'content': 'test'},
            )
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_input_missing_session_returns_404(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/agent/sessions/sess_nope/input',
                json={'content': 'test'},
            )
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_input_stopped_session_returns_409(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            r = await c.post(
                f'/w/ws_1/api/v1/agent/sessions/{sid}/input',
                json={'content': 'too late'},
            )
            assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_input_empty_content_rejected(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.post(
                f'/w/ws_1/api/v1/agent/sessions/{sid}/input',
                json={'content': ''},
            )
            assert r.status_code == 422  # Pydantic validation
