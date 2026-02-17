"""Tests for orphan session cleanup.

Bead: bd-223o.13.3 (G3)

Validates:
  - OrphanDetector correctly identifies sessions exceeding max duration.
  - cleanup_orphaned_sessions stops orphaned sessions idempotently.
  - Active sessions within limits are not affected.
  - Already-stopped sessions are ignored.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from control_plane.app.agent.cleanup import (
    OrphanDetector,
    OrphanedSession,
    cleanup_orphaned_sessions,
)
from control_plane.app.agent.sessions import (
    AgentSession,
    InMemoryAgentSessionRepository,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_session(
    session_id: str = 'sess_1',
    workspace_id: str = 'ws_1',
    age: timedelta = timedelta(hours=0),
    stopped: bool = False,
) -> AgentSession:
    now = datetime.now(timezone.utc)
    session = AgentSession(
        id=session_id,
        workspace_id=workspace_id,
        created_by='user_1',
        created_at=now - age,
    )
    if stopped:
        session.stopped_at = now
    return session


@pytest.fixture
def detector():
    return OrphanDetector(max_session_duration=timedelta(hours=24))


@pytest.fixture
def repo():
    return InMemoryAgentSessionRepository()


# =====================================================================
# OrphanDetector
# =====================================================================


class TestOrphanDetector:
    """OrphanDetector detection logic."""

    def test_young_session_not_orphaned(self, detector):
        session = _make_session(age=timedelta(hours=1))
        assert detector.is_orphaned(session) is False
        assert detector.classify(session) is None

    def test_old_session_is_orphaned(self, detector):
        session = _make_session(age=timedelta(hours=25))
        assert detector.is_orphaned(session) is True
        assert detector.classify(session) == 'max_duration_exceeded'

    def test_stopped_session_not_orphaned(self, detector):
        session = _make_session(age=timedelta(hours=48), stopped=True)
        assert detector.is_orphaned(session) is False
        assert detector.classify(session) is None

    def test_just_under_limit_not_orphaned(self, detector):
        # Slightly under 24 hours — safe margin avoids wall-clock race.
        session = _make_session(age=timedelta(hours=23, minutes=59))
        assert detector.is_orphaned(session) is False

    def test_just_over_limit_is_orphaned(self, detector):
        session = _make_session(age=timedelta(hours=24, seconds=1))
        assert detector.is_orphaned(session) is True

    def test_custom_duration(self):
        detector = OrphanDetector(max_session_duration=timedelta(minutes=30))
        young = _make_session(age=timedelta(minutes=20))
        old = _make_session(age=timedelta(minutes=31))
        assert detector.is_orphaned(young) is False
        assert detector.is_orphaned(old) is True


# =====================================================================
# cleanup_orphaned_sessions
# =====================================================================


class TestCleanupOrphanedSessions:
    """Cleanup function stops orphaned sessions."""

    @pytest.mark.asyncio
    async def test_cleanup_stops_orphaned(self, repo, detector):
        old_session = _make_session(
            session_id='sess_old', age=timedelta(hours=25),
        )
        await repo.create(old_session)

        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)
        assert len(cleaned) == 1
        assert cleaned[0].session_id == 'sess_old'
        assert cleaned[0].reason == 'max_duration_exceeded'

        # Verify session is now stopped.
        s = await repo.get('sess_old')
        assert s.is_active is False

    @pytest.mark.asyncio
    async def test_cleanup_skips_young_sessions(self, repo, detector):
        young_session = _make_session(
            session_id='sess_young', age=timedelta(hours=1),
        )
        await repo.create(young_session)

        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)
        assert len(cleaned) == 0

        # Session still active.
        s = await repo.get('sess_young')
        assert s.is_active is True

    @pytest.mark.asyncio
    async def test_cleanup_skips_already_stopped(self, repo, detector):
        stopped_session = _make_session(
            session_id='sess_stopped', age=timedelta(hours=48), stopped=True,
        )
        await repo.create(stopped_session)

        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)
        assert len(cleaned) == 0

    @pytest.mark.asyncio
    async def test_cleanup_multiple_orphans(self, repo, detector):
        for i in range(3):
            s = _make_session(
                session_id=f'sess_old_{i}', age=timedelta(hours=25 + i),
            )
            await repo.create(s)

        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)
        assert len(cleaned) == 3

    @pytest.mark.asyncio
    async def test_cleanup_is_idempotent(self, repo, detector):
        old_session = _make_session(
            session_id='sess_old', age=timedelta(hours=25),
        )
        await repo.create(old_session)

        cleaned1 = await cleanup_orphaned_sessions(repo, 'ws_1', detector)
        cleaned2 = await cleanup_orphaned_sessions(repo, 'ws_1', detector)

        assert len(cleaned1) == 1
        assert len(cleaned2) == 0  # Already stopped, no longer orphaned.

    @pytest.mark.asyncio
    async def test_cleanup_scoped_to_workspace(self, repo, detector):
        ws1_session = _make_session(
            session_id='sess_ws1', workspace_id='ws_1',
            age=timedelta(hours=25),
        )
        ws2_session = _make_session(
            session_id='sess_ws2', workspace_id='ws_2',
            age=timedelta(hours=25),
        )
        await repo.create(ws1_session)
        await repo.create(ws2_session)

        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)
        assert len(cleaned) == 1
        assert cleaned[0].workspace_id == 'ws_1'

        # ws_2 session still active.
        s2 = await repo.get('sess_ws2')
        assert s2.is_active is True

    @pytest.mark.asyncio
    async def test_cleanup_returns_orphaned_session_metadata(self, repo, detector):
        old_session = _make_session(
            session_id='sess_audit', age=timedelta(hours=30),
        )
        await repo.create(old_session)

        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)
        assert len(cleaned) == 1
        orphan = cleaned[0]
        assert isinstance(orphan, OrphanedSession)
        assert orphan.session_id == 'sess_audit'
        assert orphan.age_seconds > 0
        assert orphan.reason == 'max_duration_exceeded'
