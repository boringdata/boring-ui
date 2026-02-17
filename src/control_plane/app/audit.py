"""Audit event emitter for the control plane.

Bead: bd-223o.9.4 (C4)

Records immutable audit events for mutating operations. Each event
captures the actor, action, workspace context, request correlation ID,
and a freeform payload.

Design doc references:
  - Section 12 schema (cloud.audit_events table)
  - Section 18.8 acceptance criteria
  - Section 20.1 observability tests

Storage:
  V0 uses an in-memory store for testability. Production will write
  to the cloud.audit_events table via Supabase client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit event matching cloud.audit_events schema."""

    workspace_id: str
    user_id: str
    action: str
    request_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    id: int | None = None


# ── Emitter protocol ─────────────────────────────────────────────────


class AuditEmitter(Protocol):
    """Abstract audit event emitter."""

    async def emit(self, event: AuditEvent) -> AuditEvent: ...
    async def list_for_workspace(
        self, workspace_id: str, limit: int = 50,
    ) -> list[AuditEvent]: ...


# ── In-memory implementation ──────────────────────────────────────────


class InMemoryAuditEmitter:
    """Simple in-memory audit store for testing."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._next_id = 1

    async def emit(self, event: AuditEvent) -> AuditEvent:
        # AuditEvent is frozen, so create new with id set.
        stored = AuditEvent(
            id=self._next_id,
            workspace_id=event.workspace_id,
            user_id=event.user_id,
            action=event.action,
            request_id=event.request_id,
            payload=event.payload,
            created_at=event.created_at,
        )
        self._next_id += 1
        self._events.append(stored)
        return stored

    async def list_for_workspace(
        self, workspace_id: str, limit: int = 50,
    ) -> list[AuditEvent]:
        matching = [
            e for e in self._events
            if e.workspace_id == workspace_id
        ]
        # Most recent first.
        matching.sort(key=lambda e: e.created_at, reverse=True)
        return matching[:limit]

    @property
    def events(self) -> list[AuditEvent]:
        """Access all events (for testing assertions)."""
        return list(self._events)
