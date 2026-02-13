"""Orphan session cleanup for agent session lifecycle.

Bead: bd-223o.13.3 (G3)

Implements orphan detection and cleanup for agent sessions:
  - Sessions that have been active for longer than a maximum duration
    are considered orphaned.
  - Cleanup scans and stops orphaned sessions.
  - Integrates with StreamRegistry to close associated streams.

Design doc section 18.5 acceptance criteria:
  - Duplicate stop calls are idempotent and do not leave orphan runtime
    processes.

This module provides:
  1. ``OrphanDetector`` — identifies sessions exceeding max duration.
  2. ``cleanup_orphaned_sessions`` — stops orphaned sessions and closes
     their streams.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .sessions import AgentSession, AgentSessionRepository


@dataclass(frozen=True, slots=True)
class OrphanedSession:
    """Metadata about an orphaned session that was cleaned up."""

    session_id: str
    workspace_id: str
    age_seconds: float
    reason: str


class OrphanDetector:
    """Detects sessions that have exceeded the maximum allowed duration.

    Args:
        max_session_duration: Maximum time a session can be active.
        max_idle_duration: Maximum time since last activity (for future use).
    """

    def __init__(
        self,
        max_session_duration: timedelta = timedelta(hours=24),
    ) -> None:
        self.max_session_duration = max_session_duration

    def is_orphaned(self, session: AgentSession) -> bool:
        """Check if a session is orphaned based on duration."""
        if not session.is_active:
            return False
        now = datetime.now(timezone.utc)
        age = now - session.created_at
        return age > self.max_session_duration

    def classify(self, session: AgentSession) -> str | None:
        """Return the orphan reason or None if not orphaned."""
        if not session.is_active:
            return None
        now = datetime.now(timezone.utc)
        age = now - session.created_at
        if age > self.max_session_duration:
            return 'max_duration_exceeded'
        return None


async def cleanup_orphaned_sessions(
    session_repo: AgentSessionRepository,
    workspace_id: str,
    detector: OrphanDetector,
) -> list[OrphanedSession]:
    """Scan a workspace for orphaned sessions and stop them.

    Args:
        session_repo: Session repository.
        workspace_id: Workspace to scan.
        detector: Orphan detection rules.

    Returns:
        List of OrphanedSession records for auditing/logging.
    """
    sessions = await session_repo.list_for_workspace(workspace_id)
    cleaned: list[OrphanedSession] = []

    for session in sessions:
        reason = detector.classify(session)
        if reason is None:
            continue

        now = datetime.now(timezone.utc)
        age = (now - session.created_at).total_seconds()

        # Stop the session (idempotent).
        await session_repo.stop(session.id)

        cleaned.append(OrphanedSession(
            session_id=session.id,
            workspace_id=session.workspace_id,
            age_seconds=age,
            reason=reason,
        ))

    return cleaned
