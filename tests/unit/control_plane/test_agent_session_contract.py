"""Create-session route and payload contract tests.

Bead: bd-223o.13.1.1 (G1a)

Validates that endpoint paths and payload shapes are stable and
backward-compatible for frontend clients:
  - Endpoint path structure: /w/{workspace_id}/api/v1/agent/sessions
  - Response payload keys for create, list, stream, input, stop
  - Status codes for success and error cases
  - Session ID format (sess_ prefix)
  - created_at is ISO-8601
  - Error response structure consistency
"""

from __future__ import annotations

import re
from datetime import datetime

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
# 1. Endpoint path contract
# =====================================================================


class TestEndpointPaths:
    """Verify the exact endpoint paths exist and are routable."""

    @pytest.mark.asyncio
    async def test_create_path(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 201

    @pytest.mark.asyncio
    async def test_list_path(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_stream_path(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.get(f'/w/ws_1/api/v1/agent/sessions/{sid}/stream')
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_input_path(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.post(
                f'/w/ws_1/api/v1/agent/sessions/{sid}/input',
                json={'content': 'test'},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_stop_path(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            assert r.status_code == 200


# =====================================================================
# 2. Create response payload contract
# =====================================================================


class TestCreatePayloadContract:
    """POST response payload keys and value formats."""

    @pytest.mark.asyncio
    async def test_create_response_keys(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            data = r.json()
            assert set(data.keys()) == {
                'session_id', 'workspace_id', 'created_by', 'created_at',
            }

    @pytest.mark.asyncio
    async def test_session_id_format(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = r.json()['session_id']
            assert sid.startswith('sess_')
            assert len(sid) > 5

    @pytest.mark.asyncio
    async def test_workspace_id_matches_path(self):
        app = _make_app(members={('ws_test', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_test/api/v1/agent/sessions')
            assert r.json()['workspace_id'] == 'ws_test'

    @pytest.mark.asyncio
    async def test_created_by_matches_caller(self):
        app = _make_app(members={('ws_1', 'user_1')}, user_id='user_1')
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            assert r.json()['created_by'] == 'user_1'

    @pytest.mark.asyncio
    async def test_created_at_is_iso8601(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            ts = r.json()['created_at']
            # Should parse as ISO-8601.
            datetime.fromisoformat(ts)


# =====================================================================
# 3. List response payload contract
# =====================================================================


class TestListPayloadContract:

    @pytest.mark.asyncio
    async def test_list_response_shape(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            await c.post('/w/ws_1/api/v1/agent/sessions')
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            data = r.json()
            assert 'sessions' in data
            assert isinstance(data['sessions'], list)
            assert len(data['sessions']) == 1

    @pytest.mark.asyncio
    async def test_list_session_entry_keys(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            await c.post('/w/ws_1/api/v1/agent/sessions')
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            entry = r.json()['sessions'][0]
            assert set(entry.keys()) == {
                'session_id', 'workspace_id', 'created_by',
                'created_at', 'is_active',
            }

    @pytest.mark.asyncio
    async def test_list_empty_returns_empty_array(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            assert r.json()['sessions'] == []


# =====================================================================
# 4. Stop response payload contract
# =====================================================================


class TestStopPayloadContract:

    @pytest.mark.asyncio
    async def test_stop_response_keys(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            data = r.json()
            assert set(data.keys()) == {'session_id', 'stopped_at', 'is_active'}

    @pytest.mark.asyncio
    async def test_stop_is_active_false(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            assert r.json()['is_active'] is False

    @pytest.mark.asyncio
    async def test_stopped_at_is_iso8601(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            r = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            datetime.fromisoformat(r.json()['stopped_at'])


# =====================================================================
# 5. Error response contract
# =====================================================================


class TestErrorResponseContract:
    """All error responses must have consistent structure."""

    @pytest.mark.asyncio
    async def test_403_has_error_key(self):
        app = _make_app(members=set())
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 403
            body = r.json()
            assert 'error' in body
            assert 'detail' in body

    @pytest.mark.asyncio
    async def test_404_has_error_key(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions/sess_none/stop')
            assert r.status_code == 404
            body = r.json()
            assert body['error'] == 'session_not_found'
            assert 'detail' in body

    @pytest.mark.asyncio
    async def test_409_has_error_key(self):
        app = _make_app(members={('ws_1', 'user_1')})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            cr = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = cr.json()['session_id']
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            r = await c.get(f'/w/ws_1/api/v1/agent/sessions/{sid}/stream')
            assert r.status_code == 409
            body = r.json()
            assert body['error'] == 'session_stopped'
            assert 'detail' in body
