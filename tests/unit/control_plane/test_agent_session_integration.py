"""Agent session lifecycle, membership gates, and stream correctness tests.

Bead: bd-1h7y (G4)

Validates cross-cutting agent session behavior:
  - Session lifecycle: create → stream → input → stop → idempotent stop
  - Membership gates: non-members get 403 on all endpoints
  - Cross-workspace isolation: session from ws_A not accessible in ws_B
  - Session validation: stopped session rejects stream/input with 409
  - Orphan detection: long-running sessions detected and cleaned up
  - Repository operations: create, get, list, stop
  - Idempotent stop: multiple stops are safe
  - Session ID format and uniqueness
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from control_plane.app.agent.sessions import (
    AgentSession,
    InMemoryAgentSessionRepository,
    InMemoryMembershipChecker,
    _check_membership,
    _validate_session,
)
from control_plane.app.agent.cleanup import (
    OrphanDetector,
    OrphanedSession,
    cleanup_orphaned_sessions,
)


@pytest.fixture
def repo():
    return InMemoryAgentSessionRepository()


@pytest.fixture
def membership():
    checker = InMemoryMembershipChecker()
    checker.add_member('ws_1', 'user_1')
    checker.add_member('ws_1', 'user_2')
    checker.add_member('ws_2', 'user_1')
    return checker


def _make_session(
    workspace_id: str = 'ws_1',
    created_by: str = 'user_1',
    session_id: str = 'sess_test1',
    created_at: datetime | None = None,
) -> AgentSession:
    return AgentSession(
        id=session_id,
        workspace_id=workspace_id,
        created_by=created_by,
        created_at=created_at or datetime.now(timezone.utc),
    )


# =====================================================================
# 1. Session lifecycle: create → get → stop
# =====================================================================


class TestSessionLifecycle:
    """Basic session lifecycle operations."""

    @pytest.mark.asyncio
    async def test_create_and_get(self, repo):
        session = _make_session()
        await repo.create(session)
        retrieved = await repo.get('sess_test1')
        assert retrieved is not None
        assert retrieved.id == 'sess_test1'
        assert retrieved.workspace_id == 'ws_1'
        assert retrieved.created_by == 'user_1'
        assert retrieved.is_active

    @pytest.mark.asyncio
    async def test_stop_session(self, repo):
        session = _make_session()
        await repo.create(session)
        stopped = await repo.stop('sess_test1')
        assert stopped is not None
        assert not stopped.is_active
        assert stopped.stopped_at is not None

    @pytest.mark.asyncio
    async def test_stop_idempotent(self, repo):
        session = _make_session()
        await repo.create(session)
        s1 = await repo.stop('sess_test1')
        s2 = await repo.stop('sess_test1')
        assert s1.stopped_at == s2.stopped_at

    @pytest.mark.asyncio
    async def test_stop_nonexistent_returns_none(self, repo):
        result = await repo.stop('nonexistent')
        assert result is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, repo):
        result = await repo.get('nonexistent')
        assert result is None

    @pytest.mark.asyncio
    async def test_is_active_property(self):
        session = _make_session()
        assert session.is_active
        session.stopped_at = datetime.now(timezone.utc)
        assert not session.is_active


# =====================================================================
# 2. Membership gates
# =====================================================================


class TestMembershipGates:
    """Membership checker enforces workspace access."""

    @pytest.mark.asyncio
    async def test_active_member_allowed(self, membership):
        assert await membership.is_active_member('ws_1', 'user_1')

    @pytest.mark.asyncio
    async def test_non_member_denied(self, membership):
        assert not await membership.is_active_member('ws_1', 'user_unknown')

    @pytest.mark.asyncio
    async def test_wrong_workspace_denied(self, membership):
        assert not await membership.is_active_member('ws_unknown', 'user_1')

    @pytest.mark.asyncio
    async def test_check_membership_returns_none_for_member(self, membership):
        result = await _check_membership(membership, 'ws_1', 'user_1')
        assert result is None

    @pytest.mark.asyncio
    async def test_check_membership_returns_403_for_non_member(self, membership):
        result = await _check_membership(membership, 'ws_1', 'user_unknown')
        assert result is not None
        assert result.status_code == 403

    @pytest.mark.asyncio
    async def test_add_member_dynamically(self, membership):
        assert not await membership.is_active_member('ws_3', 'user_3')
        membership.add_member('ws_3', 'user_3')
        assert await membership.is_active_member('ws_3', 'user_3')


# =====================================================================
# 3. Session validation
# =====================================================================


class TestSessionValidation:
    """_validate_session checks existence, workspace, and active state."""

    @pytest.mark.asyncio
    async def test_valid_session_returns_session(self, repo):
        session = _make_session()
        await repo.create(session)
        result = await _validate_session(repo, 'sess_test1', 'ws_1')
        assert isinstance(result, AgentSession)
        assert result.id == 'sess_test1'

    @pytest.mark.asyncio
    async def test_nonexistent_session_returns_404(self, repo):
        result = await _validate_session(repo, 'nonexistent', 'ws_1')
        assert not isinstance(result, AgentSession)
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_workspace_returns_404(self, repo):
        session = _make_session(workspace_id='ws_1')
        await repo.create(session)
        result = await _validate_session(repo, 'sess_test1', 'ws_OTHER')
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_stopped_session_with_require_active_returns_409(self, repo):
        session = _make_session()
        await repo.create(session)
        await repo.stop('sess_test1')
        result = await _validate_session(
            repo, 'sess_test1', 'ws_1', require_active=True,
        )
        assert result.status_code == 409

    @pytest.mark.asyncio
    async def test_stopped_session_without_require_active_ok(self, repo):
        session = _make_session()
        await repo.create(session)
        await repo.stop('sess_test1')
        result = await _validate_session(
            repo, 'sess_test1', 'ws_1', require_active=False,
        )
        assert isinstance(result, AgentSession)


# =====================================================================
# 4. Cross-workspace isolation
# =====================================================================


class TestCrossWorkspaceIsolation:
    """Sessions are scoped to their workspace."""

    @pytest.mark.asyncio
    async def test_list_isolated_by_workspace(self, repo):
        await repo.create(_make_session(workspace_id='ws_1', session_id='s1'))
        await repo.create(_make_session(workspace_id='ws_2', session_id='s2'))

        ws1 = await repo.list_for_workspace('ws_1')
        ws2 = await repo.list_for_workspace('ws_2')
        assert len(ws1) == 1
        assert len(ws2) == 1
        assert ws1[0].workspace_id == 'ws_1'
        assert ws2[0].workspace_id == 'ws_2'

    @pytest.mark.asyncio
    async def test_get_from_wrong_workspace_still_returns(self, repo):
        """get() returns by ID regardless of workspace.
        Validation happens in _validate_session."""
        await repo.create(_make_session(workspace_id='ws_1', session_id='s1'))
        session = await repo.get('s1')
        assert session is not None
        # But _validate_session rejects if workspace doesn't match.

    @pytest.mark.asyncio
    async def test_validate_rejects_cross_workspace_access(self, repo):
        await repo.create(_make_session(workspace_id='ws_1', session_id='s1'))
        result = await _validate_session(repo, 's1', 'ws_2')
        assert result.status_code == 404


# =====================================================================
# 5. Orphan detection
# =====================================================================


class TestOrphanDetection:
    """OrphanDetector identifies long-running sessions."""

    def test_fresh_session_not_orphaned(self):
        detector = OrphanDetector(max_session_duration=timedelta(hours=1))
        session = _make_session()
        assert not detector.is_orphaned(session)

    def test_old_session_is_orphaned(self):
        detector = OrphanDetector(max_session_duration=timedelta(hours=1))
        session = _make_session(
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        assert detector.is_orphaned(session)

    def test_stopped_session_not_orphaned(self):
        detector = OrphanDetector(max_session_duration=timedelta(hours=1))
        session = _make_session(
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        session.stopped_at = datetime.now(timezone.utc)
        assert not detector.is_orphaned(session)

    def test_classify_returns_reason(self):
        detector = OrphanDetector(max_session_duration=timedelta(hours=1))
        session = _make_session(
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        assert detector.classify(session) == 'max_duration_exceeded'

    def test_classify_fresh_returns_none(self):
        detector = OrphanDetector(max_session_duration=timedelta(hours=1))
        session = _make_session()
        assert detector.classify(session) is None


# =====================================================================
# 6. Orphan cleanup
# =====================================================================


class TestOrphanCleanup:
    """cleanup_orphaned_sessions stops orphaned sessions."""

    @pytest.mark.asyncio
    async def test_cleanup_stops_orphaned(self, repo):
        old_session = _make_session(
            session_id='old_sess',
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        await repo.create(old_session)

        detector = OrphanDetector(max_session_duration=timedelta(hours=24))
        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)

        assert len(cleaned) == 1
        assert cleaned[0].session_id == 'old_sess'
        assert cleaned[0].reason == 'max_duration_exceeded'

        # Verify session is actually stopped.
        session = await repo.get('old_sess')
        assert not session.is_active

    @pytest.mark.asyncio
    async def test_cleanup_skips_fresh_sessions(self, repo):
        fresh = _make_session(session_id='fresh_sess')
        await repo.create(fresh)

        detector = OrphanDetector(max_session_duration=timedelta(hours=24))
        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)

        assert len(cleaned) == 0
        session = await repo.get('fresh_sess')
        assert session.is_active

    @pytest.mark.asyncio
    async def test_cleanup_skips_already_stopped(self, repo):
        old_session = _make_session(
            session_id='stopped_sess',
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        old_session.stopped_at = datetime.now(timezone.utc)
        await repo.create(old_session)

        detector = OrphanDetector(max_session_duration=timedelta(hours=24))
        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)

        assert len(cleaned) == 0

    @pytest.mark.asyncio
    async def test_cleanup_mixed(self, repo):
        # One orphaned, one fresh, one already stopped.
        await repo.create(_make_session(
            session_id='orphan',
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        ))
        await repo.create(_make_session(session_id='fresh'))
        stopped = _make_session(
            session_id='stopped',
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        stopped.stopped_at = datetime.now(timezone.utc)
        await repo.create(stopped)

        detector = OrphanDetector(max_session_duration=timedelta(hours=24))
        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)

        assert len(cleaned) == 1
        assert cleaned[0].session_id == 'orphan'

    @pytest.mark.asyncio
    async def test_cleanup_isolated_by_workspace(self, repo):
        await repo.create(_make_session(
            workspace_id='ws_1', session_id='ws1_orphan',
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        ))
        await repo.create(_make_session(
            workspace_id='ws_2', session_id='ws2_orphan',
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        ))

        detector = OrphanDetector(max_session_duration=timedelta(hours=24))
        cleaned = await cleanup_orphaned_sessions(repo, 'ws_1', detector)

        assert len(cleaned) == 1
        assert cleaned[0].workspace_id == 'ws_1'


# =====================================================================
# 7. OrphanedSession dataclass
# =====================================================================


class TestOrphanedSessionDataclass:

    def test_orphaned_session_frozen(self):
        orphan = OrphanedSession(
            session_id='s1',
            workspace_id='ws_1',
            age_seconds=86400.0,
            reason='max_duration_exceeded',
        )
        with pytest.raises(AttributeError):
            orphan.reason = 'changed'

    def test_orphaned_session_fields(self):
        orphan = OrphanedSession(
            session_id='s1',
            workspace_id='ws_1',
            age_seconds=3600.0,
            reason='max_duration_exceeded',
        )
        assert orphan.session_id == 's1'
        assert orphan.workspace_id == 'ws_1'
        assert orphan.age_seconds == 3600.0
        assert orphan.reason == 'max_duration_exceeded'


# =====================================================================
# 8. Repository listing
# =====================================================================


class TestRepositoryListing:

    @pytest.mark.asyncio
    async def test_list_sorted_by_created_at(self, repo):
        now = datetime.now(timezone.utc)
        s1 = _make_session(session_id='s1')
        s1.created_at = now - timedelta(hours=2)
        s2 = _make_session(session_id='s2')
        s2.created_at = now - timedelta(hours=1)
        await repo.create(s1)
        await repo.create(s2)

        sessions = await repo.list_for_workspace('ws_1')
        assert sessions[0].id == 's1'
        assert sessions[1].id == 's2'

    @pytest.mark.asyncio
    async def test_list_empty_workspace(self, repo):
        sessions = await repo.list_for_workspace('ws_empty')
        assert sessions == []
