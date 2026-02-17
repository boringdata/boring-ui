"""Tests for share-access audit events and log redaction.

Bead: bd-223o.12.4 (F4)

Validates:
  - Token redaction never leaks plaintext tokens.
  - String redaction replaces token-like sequences.
  - Audit events record correct metadata for each operation type.
  - InMemoryShareAuditEmitter filters by type and workspace.
  - Event serialization produces safe-for-logging dicts.
"""

from __future__ import annotations

import pytest

from control_plane.app.sharing.audit import (
    InMemoryShareAuditEmitter,
    ShareAuditEvent,
    TOKEN_PREFIX_LENGTH,
    emit_share_accessed,
    emit_share_created,
    emit_share_denied,
    emit_share_revoked,
    emit_share_write,
    redact_string,
    redact_token,
)
from control_plane.app.sharing.model import generate_share_token


# =====================================================================
# Token redaction
# =====================================================================


class TestRedactToken:
    """redact_token safety."""

    def test_long_token_truncated(self):
        token = generate_share_token()
        result = redact_token(token)
        assert result.endswith('...')
        assert len(result) == TOKEN_PREFIX_LENGTH + 3
        assert token not in result

    def test_none_returns_redacted(self):
        assert redact_token(None) == '<redacted>'

    def test_empty_returns_redacted(self):
        assert redact_token('') == '<redacted>'

    def test_short_token_returns_redacted(self):
        assert redact_token('abc') == '<redacted>'

    def test_prefix_matches_original(self):
        token = 'abcdefghijklmnop'
        result = redact_token(token)
        assert result.startswith(token[:TOKEN_PREFIX_LENGTH])


class TestRedactString:
    """redact_string replaces token-like sequences."""

    def test_redacts_token_in_message(self):
        token = generate_share_token()
        msg = f'Access denied for token {token}'
        result = redact_string(msg)
        assert token not in result
        assert '...' in result

    def test_preserves_short_strings(self):
        msg = 'Normal log message without tokens'
        assert redact_string(msg) == msg

    def test_redacts_multiple_tokens(self):
        t1 = generate_share_token()
        t2 = generate_share_token()
        msg = f'Compare {t1} and {t2}'
        result = redact_string(msg)
        assert t1 not in result
        assert t2 not in result

    def test_preserves_non_token_long_strings(self):
        msg = 'This is a long message with spaces and punctuation!'
        assert redact_string(msg) == msg


# =====================================================================
# ShareAuditEvent
# =====================================================================


class TestShareAuditEvent:
    """Event model and serialization."""

    def test_to_dict_contains_all_fields(self):
        event = ShareAuditEvent(
            event_type='share.created',
            workspace_id='ws_1',
            share_id=42,
            token_prefix='abcdefgh...',
            path='/docs/README.md',
            access='read',
            actor_user_id='user_1',
        )
        d = event.to_dict()
        assert d['event_type'] == 'share.created'
        assert d['workspace_id'] == 'ws_1'
        assert d['share_id'] == 42
        assert d['token_prefix'] == 'abcdefgh...'
        assert d['path'] == '/docs/README.md'
        assert d['timestamp']  # ISO format.

    def test_to_dict_safe_for_json(self):
        """All values are JSON-serializable primitives."""
        event = ShareAuditEvent(
            event_type='share.denied',
            workspace_id='ws_2',
            detail='expired',
        )
        d = event.to_dict()
        import json
        json.dumps(d)  # Must not raise.

    def test_no_plaintext_token_in_event(self):
        """Token prefix never contains a full token."""
        token = generate_share_token()
        event = ShareAuditEvent(
            event_type='share.accessed',
            workspace_id='ws_1',
            token_prefix=redact_token(token),
        )
        assert token not in event.token_prefix
        d = event.to_dict()
        assert token not in str(d)


# =====================================================================
# InMemoryShareAuditEmitter
# =====================================================================


class TestInMemoryEmitter:
    """In-memory audit emitter for testing."""

    @pytest.mark.asyncio
    async def test_emit_stores_event(self):
        emitter = InMemoryShareAuditEmitter()
        event = ShareAuditEvent(event_type='share.created', workspace_id='ws_1')
        await emitter.emit(event)
        assert len(emitter.events) == 1

    @pytest.mark.asyncio
    async def test_find_by_type(self):
        emitter = InMemoryShareAuditEmitter()
        await emitter.emit(ShareAuditEvent(event_type='share.created', workspace_id='ws_1'))
        await emitter.emit(ShareAuditEvent(event_type='share.denied', workspace_id='ws_1'))
        assert len(emitter.find(event_type='share.created')) == 1
        assert len(emitter.find(event_type='share.denied')) == 1

    @pytest.mark.asyncio
    async def test_find_by_workspace(self):
        emitter = InMemoryShareAuditEmitter()
        await emitter.emit(ShareAuditEvent(event_type='share.created', workspace_id='ws_1'))
        await emitter.emit(ShareAuditEvent(event_type='share.created', workspace_id='ws_2'))
        assert len(emitter.find(workspace_id='ws_1')) == 1

    @pytest.mark.asyncio
    async def test_find_by_type_and_workspace(self):
        emitter = InMemoryShareAuditEmitter()
        await emitter.emit(ShareAuditEvent(event_type='share.created', workspace_id='ws_1'))
        await emitter.emit(ShareAuditEvent(event_type='share.denied', workspace_id='ws_1'))
        await emitter.emit(ShareAuditEvent(event_type='share.created', workspace_id='ws_2'))
        assert len(emitter.find(event_type='share.created', workspace_id='ws_1')) == 1


# =====================================================================
# Convenience emitters
# =====================================================================


class TestConvenienceEmitters:
    """emit_share_* convenience functions."""

    @pytest.mark.asyncio
    async def test_emit_share_created(self):
        emitter = InMemoryShareAuditEmitter()
        token = generate_share_token()
        event = await emit_share_created(
            emitter,
            workspace_id='ws_1',
            share_id=1,
            token=token,
            path='/docs/README.md',
            access='read',
            user_id='user_1',
        )
        assert event.event_type == 'share.created'
        assert event.share_id == 1
        assert event.actor_user_id == 'user_1'
        assert token not in event.token_prefix
        assert len(emitter.events) == 1

    @pytest.mark.asyncio
    async def test_emit_share_accessed(self):
        emitter = InMemoryShareAuditEmitter()
        token = generate_share_token()
        event = await emit_share_accessed(
            emitter,
            workspace_id='ws_1',
            share_id=2,
            token=token,
            path='/file.txt',
            access='read',
        )
        assert event.event_type == 'share.accessed'
        assert token not in event.token_prefix

    @pytest.mark.asyncio
    async def test_emit_share_write(self):
        emitter = InMemoryShareAuditEmitter()
        token = generate_share_token()
        event = await emit_share_write(
            emitter,
            workspace_id='ws_1',
            share_id=3,
            token=token,
            path='/file.txt',
        )
        assert event.event_type == 'share.write'
        assert event.access == 'write'

    @pytest.mark.asyncio
    async def test_emit_share_revoked(self):
        emitter = InMemoryShareAuditEmitter()
        event = await emit_share_revoked(
            emitter,
            workspace_id='ws_1',
            share_id=4,
            path='/file.txt',
            user_id='user_1',
        )
        assert event.event_type == 'share.revoked'
        assert event.actor_user_id == 'user_1'

    @pytest.mark.asyncio
    async def test_emit_share_denied(self):
        emitter = InMemoryShareAuditEmitter()
        token = generate_share_token()
        event = await emit_share_denied(
            emitter,
            workspace_id='ws_1',
            token=token,
            path='/secret.txt',
            detail='expired',
        )
        assert event.event_type == 'share.denied'
        assert event.detail == 'expired'
        assert token not in event.token_prefix


# =====================================================================
# Security invariant: no plaintext leak
# =====================================================================


class TestNoPlaintextLeak:
    """Ensure no audit pathway leaks full plaintext tokens."""

    @pytest.mark.asyncio
    async def test_created_event_no_leak(self):
        emitter = InMemoryShareAuditEmitter()
        token = generate_share_token()
        event = await emit_share_created(
            emitter, workspace_id='ws_1', share_id=1,
            token=token, path='/f.txt', access='read', user_id='u1',
        )
        serialized = str(event.to_dict())
        assert token not in serialized

    @pytest.mark.asyncio
    async def test_accessed_event_no_leak(self):
        emitter = InMemoryShareAuditEmitter()
        token = generate_share_token()
        event = await emit_share_accessed(
            emitter, workspace_id='ws_1', share_id=1,
            token=token, path='/f.txt', access='read',
        )
        serialized = str(event.to_dict())
        assert token not in serialized

    @pytest.mark.asyncio
    async def test_denied_event_no_leak(self):
        emitter = InMemoryShareAuditEmitter()
        token = generate_share_token()
        event = await emit_share_denied(
            emitter, workspace_id='ws_1',
            token=token, detail='scope violation',
        )
        serialized = str(event.to_dict())
        assert token not in serialized
