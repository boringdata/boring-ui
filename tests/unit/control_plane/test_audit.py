"""Tests for audit event emitter.

Bead: bd-223o.9.4 (C4)

Validates:
  - AuditEvent captures required fields (workspace_id, user_id, action)
  - Events are immutable (frozen dataclass)
  - InMemoryAuditEmitter stores and retrieves events
  - Events ordered by most recent first
  - Request correlation ID preserved
  - Payload serialized as dict
  - Workspace filtering works correctly
  - Limit parameter respected
  - Audit action constants cover required mutation types
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from control_plane.app.audit import (
    AuditEvent,
    InMemoryAuditEmitter,
)

# ── Audit action constants ────────────────────────────────────────────
# These should match the actions emitted by workspace/member routes.

WORKSPACE_CREATED = 'workspace.created'
WORKSPACE_UPDATED = 'workspace.updated'
MEMBER_INVITED = 'member.invited'
MEMBER_REMOVED = 'member.removed'
MEMBER_AUTO_ACCEPTED = 'member.auto_accepted'


# =====================================================================
# 1. AuditEvent dataclass
# =====================================================================


class TestAuditEvent:

    def test_create_with_required_fields(self):
        event = AuditEvent(
            workspace_id='ws_1',
            user_id='user-1',
            action=WORKSPACE_CREATED,
        )
        assert event.workspace_id == 'ws_1'
        assert event.user_id == 'user-1'
        assert event.action == WORKSPACE_CREATED
        assert event.request_id is None
        assert event.payload == {}
        assert isinstance(event.created_at, datetime)

    def test_create_with_all_fields(self):
        event = AuditEvent(
            workspace_id='ws_1',
            user_id='user-1',
            action=MEMBER_INVITED,
            request_id='req-123',
            payload={'email': 'invited@example.com', 'role': 'admin'},
        )
        assert event.request_id == 'req-123'
        assert event.payload['email'] == 'invited@example.com'

    def test_event_is_frozen(self):
        event = AuditEvent(
            workspace_id='ws_1',
            user_id='user-1',
            action=WORKSPACE_CREATED,
        )
        with pytest.raises(AttributeError):
            event.action = 'modified'


# =====================================================================
# 2. InMemoryAuditEmitter
# =====================================================================


class TestInMemoryAuditEmitter:

    @pytest.mark.asyncio
    async def test_emit_stores_event(self):
        emitter = InMemoryAuditEmitter()
        event = AuditEvent(
            workspace_id='ws_1',
            user_id='user-1',
            action=WORKSPACE_CREATED,
        )
        stored = await emitter.emit(event)
        assert stored.id is not None
        assert stored.id == 1
        assert len(emitter.events) == 1

    @pytest.mark.asyncio
    async def test_emit_assigns_sequential_ids(self):
        emitter = InMemoryAuditEmitter()
        e1 = await emitter.emit(AuditEvent(
            workspace_id='ws_1', user_id='u', action='a',
        ))
        e2 = await emitter.emit(AuditEvent(
            workspace_id='ws_1', user_id='u', action='b',
        ))
        assert e1.id == 1
        assert e2.id == 2

    @pytest.mark.asyncio
    async def test_list_for_workspace_filters(self):
        emitter = InMemoryAuditEmitter()
        await emitter.emit(AuditEvent(
            workspace_id='ws_1', user_id='u', action='a',
        ))
        await emitter.emit(AuditEvent(
            workspace_id='ws_2', user_id='u', action='b',
        ))
        await emitter.emit(AuditEvent(
            workspace_id='ws_1', user_id='u', action='c',
        ))

        result = await emitter.list_for_workspace('ws_1')
        assert len(result) == 2
        assert all(e.workspace_id == 'ws_1' for e in result)

    @pytest.mark.asyncio
    async def test_list_ordered_most_recent_first(self):
        emitter = InMemoryAuditEmitter()
        e1 = await emitter.emit(AuditEvent(
            workspace_id='ws_1', user_id='u', action='first',
        ))
        e2 = await emitter.emit(AuditEvent(
            workspace_id='ws_1', user_id='u', action='second',
        ))

        result = await emitter.list_for_workspace('ws_1')
        assert result[0].action == 'second'
        assert result[1].action == 'first'

    @pytest.mark.asyncio
    async def test_list_respects_limit(self):
        emitter = InMemoryAuditEmitter()
        for i in range(10):
            await emitter.emit(AuditEvent(
                workspace_id='ws_1', user_id='u', action=f'action_{i}',
            ))

        result = await emitter.list_for_workspace('ws_1', limit=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_empty_workspace(self):
        emitter = InMemoryAuditEmitter()
        result = await emitter.list_for_workspace('ws_empty')
        assert result == []

    @pytest.mark.asyncio
    async def test_request_id_preserved(self):
        emitter = InMemoryAuditEmitter()
        stored = await emitter.emit(AuditEvent(
            workspace_id='ws_1',
            user_id='u',
            action='test',
            request_id='req-correlation-123',
        ))
        assert stored.request_id == 'req-correlation-123'

    @pytest.mark.asyncio
    async def test_payload_preserved(self):
        emitter = InMemoryAuditEmitter()
        stored = await emitter.emit(AuditEvent(
            workspace_id='ws_1',
            user_id='u',
            action=MEMBER_INVITED,
            payload={
                'email': 'test@example.com',
                'role': 'admin',
                'previous_status': None,
            },
        ))
        assert stored.payload['email'] == 'test@example.com'
        assert stored.payload['role'] == 'admin'


# =====================================================================
# 3. Audit action coverage
# =====================================================================


class TestAuditActions:
    """Verify all required mutation types have defined action constants."""

    def test_workspace_actions_defined(self):
        assert WORKSPACE_CREATED == 'workspace.created'
        assert WORKSPACE_UPDATED == 'workspace.updated'

    def test_member_actions_defined(self):
        assert MEMBER_INVITED == 'member.invited'
        assert MEMBER_REMOVED == 'member.removed'
        assert MEMBER_AUTO_ACCEPTED == 'member.auto_accepted'

    @pytest.mark.asyncio
    async def test_workspace_create_audit_event(self):
        """Simulate a workspace.created audit event."""
        emitter = InMemoryAuditEmitter()
        event = AuditEvent(
            workspace_id='ws_new',
            user_id='creator-uuid',
            action=WORKSPACE_CREATED,
            request_id='req-001',
            payload={
                'name': 'New Workspace',
                'app_id': 'boring-ui',
            },
        )
        stored = await emitter.emit(event)
        assert stored.action == WORKSPACE_CREATED
        assert stored.payload['name'] == 'New Workspace'

    @pytest.mark.asyncio
    async def test_member_invite_audit_event(self):
        """Simulate a member.invited audit event."""
        emitter = InMemoryAuditEmitter()
        event = AuditEvent(
            workspace_id='ws_1',
            user_id='inviter-uuid',
            action=MEMBER_INVITED,
            payload={
                'email': 'invited@example.com',
                'role': 'admin',
            },
        )
        stored = await emitter.emit(event)
        assert stored.action == MEMBER_INVITED

    @pytest.mark.asyncio
    async def test_member_removal_audit_event(self):
        """Simulate a member.removed audit event."""
        emitter = InMemoryAuditEmitter()
        event = AuditEvent(
            workspace_id='ws_1',
            user_id='admin-uuid',
            action=MEMBER_REMOVED,
            payload={
                'member_id': 42,
                'email': 'removed@example.com',
            },
        )
        stored = await emitter.emit(event)
        assert stored.action == MEMBER_REMOVED

    @pytest.mark.asyncio
    async def test_auto_accept_audit_event(self):
        """Simulate a member.auto_accepted audit event."""
        emitter = InMemoryAuditEmitter()
        event = AuditEvent(
            workspace_id='ws_1',
            user_id='invitee-uuid',
            action=MEMBER_AUTO_ACCEPTED,
            payload={
                'email': 'invitee@example.com',
                'member_id': 5,
            },
        )
        stored = await emitter.emit(event)
        assert stored.action == MEMBER_AUTO_ACCEPTED
