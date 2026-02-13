"""Share-access audit events and log redaction.

Bead: bd-223o.12.4 (F4)

Implements audit event recording for share operations from Feature 3
design doc section 18.6:

  - Record share create, access (read/write), revoke operations.
  - Redact plaintext tokens from all event payloads.
  - Provide structured audit records for observability pipelines.

Security invariant:
  Plaintext tokens must NEVER appear in audit event data.
  Only token prefixes (first 8 chars) are included for correlation.

This module provides:
  1. ``ShareAuditEvent`` — structured audit record.
  2. ``ShareAuditEmitter`` — protocol for event sinks.
  3. ``InMemoryShareAuditEmitter`` — test implementation.
  4. ``redact_token`` — safely truncate tokens for logging.
  5. ``emit_share_*`` — convenience functions for each operation type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

# ── Constants ─────────────────────────────────────────────────────────

TOKEN_PREFIX_LENGTH = 8  # Characters to keep for correlation.

# Pattern for URL-safe base64 tokens (44+ chars from token_urlsafe(32)).
_TOKEN_PATTERN = re.compile(r'[A-Za-z0-9_-]{20,}')


# ── Token redaction ──────────────────────────────────────────────────


def redact_token(token: str | None) -> str:
    """Safely truncate a token to a prefix for logging.

    Returns ``<prefix>...`` or ``<redacted>`` for missing/short tokens.
    """
    if not token or len(token) < TOKEN_PREFIX_LENGTH:
        return '<redacted>'
    return f'{token[:TOKEN_PREFIX_LENGTH]}...'


def redact_string(text: str) -> str:
    """Replace any token-like strings in text with redacted versions.

    Identifies URL-safe base64 sequences >= 20 chars and replaces with
    their prefix + ``...``.
    """
    def _replace(match: re.Match) -> str:
        return redact_token(match.group(0))

    return _TOKEN_PATTERN.sub(_replace, text)


# ── Audit event model ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ShareAuditEvent:
    """Structured audit event for share operations.

    Attributes:
        event_type: Operation type (share.created, share.accessed,
                    share.write, share.revoked, share.denied).
        workspace_id: Which workspace this relates to.
        share_id: Numeric share link ID (if known).
        token_prefix: First 8 chars of the token (for correlation only).
        path: The file path involved.
        access: Access mode (read/write).
        actor_user_id: Who performed the action (if authenticated).
        detail: Additional context (e.g., denial reason).
        timestamp: When the event occurred.
    """

    event_type: str
    workspace_id: str
    share_id: int | None = None
    token_prefix: str = '<redacted>'
    path: str = ''
    access: str = ''
    actor_user_id: str = ''
    detail: str = ''
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        """Serialize to a dict safe for JSON logging."""
        return {
            'event_type': self.event_type,
            'workspace_id': self.workspace_id,
            'share_id': self.share_id,
            'token_prefix': self.token_prefix,
            'path': self.path,
            'access': self.access,
            'actor_user_id': self.actor_user_id,
            'detail': self.detail,
            'timestamp': self.timestamp.isoformat(),
        }


# ── Emitter protocol ────────────────────────────────────────────────


class ShareAuditEmitter(Protocol):
    """Abstract audit event sink."""

    async def emit(self, event: ShareAuditEvent) -> None: ...


# ── In-memory implementation ────────────────────────────────────────


class InMemoryShareAuditEmitter:
    """Test audit emitter that stores events in memory."""

    def __init__(self) -> None:
        self.events: list[ShareAuditEvent] = []

    async def emit(self, event: ShareAuditEvent) -> None:
        self.events.append(event)

    def find(
        self,
        event_type: str | None = None,
        workspace_id: str | None = None,
    ) -> list[ShareAuditEvent]:
        """Filter events by type and/or workspace."""
        result = self.events
        if event_type:
            result = [e for e in result if e.event_type == event_type]
        if workspace_id:
            result = [e for e in result if e.workspace_id == workspace_id]
        return result


# ── Convenience emitters ─────────────────────────────────────────────


async def emit_share_created(
    emitter: ShareAuditEmitter,
    *,
    workspace_id: str,
    share_id: int,
    token: str,
    path: str,
    access: str,
    user_id: str,
) -> ShareAuditEvent:
    """Emit a share.created audit event."""
    event = ShareAuditEvent(
        event_type='share.created',
        workspace_id=workspace_id,
        share_id=share_id,
        token_prefix=redact_token(token),
        path=path,
        access=access,
        actor_user_id=user_id,
    )
    await emitter.emit(event)
    return event


async def emit_share_accessed(
    emitter: ShareAuditEmitter,
    *,
    workspace_id: str,
    share_id: int,
    token: str,
    path: str,
    access: str,
) -> ShareAuditEvent:
    """Emit a share.accessed audit event (read operation)."""
    event = ShareAuditEvent(
        event_type='share.accessed',
        workspace_id=workspace_id,
        share_id=share_id,
        token_prefix=redact_token(token),
        path=path,
        access=access,
    )
    await emitter.emit(event)
    return event


async def emit_share_write(
    emitter: ShareAuditEmitter,
    *,
    workspace_id: str,
    share_id: int,
    token: str,
    path: str,
) -> ShareAuditEvent:
    """Emit a share.write audit event."""
    event = ShareAuditEvent(
        event_type='share.write',
        workspace_id=workspace_id,
        share_id=share_id,
        token_prefix=redact_token(token),
        path=path,
        access='write',
    )
    await emitter.emit(event)
    return event


async def emit_share_revoked(
    emitter: ShareAuditEmitter,
    *,
    workspace_id: str,
    share_id: int,
    path: str,
    user_id: str,
) -> ShareAuditEvent:
    """Emit a share.revoked audit event."""
    event = ShareAuditEvent(
        event_type='share.revoked',
        workspace_id=workspace_id,
        share_id=share_id,
        path=path,
        actor_user_id=user_id,
    )
    await emitter.emit(event)
    return event


async def emit_share_denied(
    emitter: ShareAuditEmitter,
    *,
    workspace_id: str,
    token: str,
    path: str = '',
    detail: str = '',
) -> ShareAuditEvent:
    """Emit a share.denied audit event."""
    event = ShareAuditEvent(
        event_type='share.denied',
        workspace_id=workspace_id,
        token_prefix=redact_token(token),
        path=path,
        detail=detail,
    )
    await emitter.emit(event)
    return event
