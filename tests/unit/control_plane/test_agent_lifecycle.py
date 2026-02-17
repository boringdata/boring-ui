"""Integration tests for agent session full lifecycle and duplicate stop behavior.

Bead: bd-223o.13.3.1 (G3a)

Validates:
  - Full lifecycle: create → stream → input → stop → verify stopped.
  - Duplicate stop: stop called 3x → only first actually stops, all return same timestamp.
  - Stream after stop returns 409.
  - Input after stop returns 409.
  - Orphan cleanup integration with active/stopped mix.
  - Multiple independent sessions in same workspace.
  - Cleanup + stop interplay: cleanup stops orphan, subsequent API stop is idempotent.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from control_plane.app.agent.sessions import (
    InMemoryAgentSessionRepository,
    InMemoryMembershipChecker,
    create_agent_session_router,
)
from control_plane.app.agent.cleanup import (
    OrphanDetector,
    cleanup_orphaned_sessions,
)
from control_plane.app.security.token_verify import AuthIdentity


# ── Test app ──────────────────────────────────────────────────────────


def _make_app() -> tuple[FastAPI, InMemoryAgentSessionRepository]:
    """Build a test app with agent session routes."""
    app = FastAPI()
    repo = InMemoryAgentSessionRepository()
    checker = InMemoryMembershipChecker({('ws_1', 'user_1')})

    router = create_agent_session_router(repo, checker)
    app.include_router(router)

    @app.middleware('http')
    async def fake_auth(request: Request, call_next):
        request.state.auth_identity = AuthIdentity(
            user_id='user_1', email='u@t.com', role='authenticated',
        )
        return await call_next(request)

    app.state.session_repo = repo
    return app, repo


@pytest.fixture
def app_and_repo():
    return _make_app()


# =====================================================================
# Full lifecycle
# =====================================================================


class TestFullLifecycle:
    """Create → stream → input → stop → verify."""

    @pytest.mark.asyncio
    async def test_create_stream_input_stop(self, app_and_repo):
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # Create.
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 201
            sid = r.json()['session_id']

            # Stream.
            r = await c.get(f'/w/ws_1/api/v1/agent/sessions/{sid}/stream')
            assert r.status_code == 200
            assert r.json()['stream'] == 'connected'

            # Input.
            r = await c.post(
                f'/w/ws_1/api/v1/agent/sessions/{sid}/input',
                json={'content': 'hello'},
            )
            assert r.status_code == 200
            assert r.json()['accepted'] is True

            # Stop.
            r = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            assert r.status_code == 200
            assert r.json()['is_active'] is False

            # Verify session is stopped.
            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            sessions = r.json()['sessions']
            assert len(sessions) == 1
            assert sessions[0]['is_active'] is False

    @pytest.mark.asyncio
    async def test_stream_after_stop_returns_409(self, app_and_repo):
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = r.json()['session_id']
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')

            r = await c.get(f'/w/ws_1/api/v1/agent/sessions/{sid}/stream')
            assert r.status_code == 409
            assert r.json()['error'] == 'session_stopped'

    @pytest.mark.asyncio
    async def test_input_after_stop_returns_409(self, app_and_repo):
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = r.json()['session_id']
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')

            r = await c.post(
                f'/w/ws_1/api/v1/agent/sessions/{sid}/input',
                json={'content': 'too late'},
            )
            assert r.status_code == 409


# =====================================================================
# Duplicate stop
# =====================================================================


class TestDuplicateStop:
    """Stop called multiple times returns consistent result."""

    @pytest.mark.asyncio
    async def test_triple_stop_same_timestamp(self, app_and_repo):
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = r.json()['session_id']

            r1 = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            r2 = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            r3 = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')

            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r3.status_code == 200
            assert r1.json()['stopped_at'] == r2.json()['stopped_at']
            assert r2.json()['stopped_at'] == r3.json()['stopped_at']
            assert r1.json()['is_active'] is False

    @pytest.mark.asyncio
    async def test_stop_preserves_first_timestamp(self, app_and_repo):
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = r.json()['session_id']

            r1 = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            first_ts = r1.json()['stopped_at']

            # Even after multiple stops, timestamp is stable.
            for _ in range(5):
                r = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
                assert r.json()['stopped_at'] == first_ts


# =====================================================================
# Multiple sessions
# =====================================================================


class TestMultipleSessions:
    """Independent sessions in same workspace."""

    @pytest.mark.asyncio
    async def test_three_independent_sessions(self, app_and_repo):
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            sids = []
            for _ in range(3):
                r = await c.post('/w/ws_1/api/v1/agent/sessions')
                sids.append(r.json()['session_id'])

            # All unique.
            assert len(set(sids)) == 3

            # Stop first, others still active.
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sids[0]}/stop')

            r = await c.get('/w/ws_1/api/v1/agent/sessions')
            sessions = r.json()['sessions']
            active = [s for s in sessions if s['is_active']]
            stopped = [s for s in sessions if not s['is_active']]
            assert len(active) == 2
            assert len(stopped) == 1

    @pytest.mark.asyncio
    async def test_stop_one_doesnt_affect_others(self, app_and_repo):
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r1 = await c.post('/w/ws_1/api/v1/agent/sessions')
            r2 = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid1 = r1.json()['session_id']
            sid2 = r2.json()['session_id']

            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid1}/stop')

            # Second session still streams.
            r = await c.get(f'/w/ws_1/api/v1/agent/sessions/{sid2}/stream')
            assert r.status_code == 200
            assert r.json()['stream'] == 'connected'


# =====================================================================
# Cleanup + stop interplay
# =====================================================================


class TestCleanupStopInterplay:
    """Orphan cleanup and API stop work together."""

    @pytest.mark.asyncio
    async def test_cleanup_then_api_stop_idempotent(self, app_and_repo):
        """Cleanup stops orphan; subsequent API stop returns same timestamp."""
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = r.json()['session_id']

            # Manually age the session to make it orphaned.
            session = await repo.get(sid)
            session.created_at = session.created_at - timedelta(hours=25)

            detector = OrphanDetector(max_session_duration=timedelta(hours=24))
            cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)
            assert len(cleaned) == 1

            # API stop should return the same stopped state.
            r = await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')
            assert r.status_code == 200
            assert r.json()['is_active'] is False

    @pytest.mark.asyncio
    async def test_cleanup_skips_already_api_stopped(self, app_and_repo):
        """Session stopped via API is not flagged as orphan."""
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post('/w/ws_1/api/v1/agent/sessions')
            sid = r.json()['session_id']

            # Stop via API.
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sid}/stop')

            # Age it (already stopped, so cleanup should skip).
            session = await repo.get(sid)
            session.created_at = session.created_at - timedelta(hours=25)

            detector = OrphanDetector(max_session_duration=timedelta(hours=24))
            cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)
            assert len(cleaned) == 0

    @pytest.mark.asyncio
    async def test_mixed_active_stopped_cleanup(self, app_and_repo):
        """Cleanup only targets active orphans, leaves young and stopped alone."""
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # Create 3 sessions.
            sids = []
            for _ in range(3):
                r = await c.post('/w/ws_1/api/v1/agent/sessions')
                sids.append(r.json()['session_id'])

            # Age first (orphan), stop second (not orphan), leave third (young).
            s0 = await repo.get(sids[0])
            s0.created_at = s0.created_at - timedelta(hours=25)
            await c.post(f'/w/ws_1/api/v1/agent/sessions/{sids[1]}/stop')

            detector = OrphanDetector(max_session_duration=timedelta(hours=24))
            cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)

            assert len(cleaned) == 1
            assert cleaned[0].session_id == sids[0]

            # Third session still active.
            s2 = await repo.get(sids[2])
            assert s2.is_active is True
