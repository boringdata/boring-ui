"""Audit event persistence layer for compliance and forensics (bd-1pwb.9.2).

Provides:
- Pluggable audit storage backends (memory, file, database)
- Query interface for audit trail retrieval
- Compliance-grade event retention
- Searchable audit logs
"""

import json
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any, List, Dict
from dataclasses import asdict

from .audit import AuditEvent, AuditEventType


class AuditStore(ABC):
    """Abstract audit event storage backend."""

    @abstractmethod
    def store(self, event: AuditEvent) -> None:
        """Store an audit event.

        Args:
            event: AuditEvent to persist

        Raises:
            Exception: If storage fails (must be logged but not raise to caller)
        """
        pass

    @abstractmethod
    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """Query audit events.

        Args:
            event_type: Filter by event type
            user_id: Filter by user ID
            workspace_id: Filter by workspace ID
            trace_id: Filter by trace/request ID
            status: Filter by status (success, failure, denied)
            since: Filter events after timestamp
            until: Filter events before timestamp
            limit: Maximum results to return

        Returns:
            List of matching AuditEvent objects
        """
        pass

    @abstractmethod
    def count(
        self,
        event_type: Optional[AuditEventType] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Count audit events matching criteria.

        Args:
            event_type: Filter by event type
            status: Filter by status (success, failure, denied)
            since: Filter events after timestamp

        Returns:
            Count of matching events
        """
        pass


class InMemoryAuditStore(AuditStore):
    """In-memory audit event store (ephemeral).

    Suitable for development and testing. Events are lost on restart.
    Thread-safe using locks.
    """

    def __init__(self, max_events: int = 10000):
        """Initialize in-memory store.

        Args:
            max_events: Maximum events to keep in memory (FIFO eviction)
        """
        self.events: List[AuditEvent] = []
        self.max_events = max_events
        self._lock = threading.Lock()

    def store(self, event: AuditEvent) -> None:
        """Store event in memory."""
        with self._lock:
            self.events.append(event)
            # FIFO eviction if exceeding max
            if len(self.events) > self.max_events:
                self.events.pop(0)

    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """Query in-memory events."""
        with self._lock:
            results = self.events

            # Apply filters
            if event_type:
                results = [e for e in results if e.event_type == event_type]
            if user_id:
                results = [e for e in results if e.user_id == user_id]
            if workspace_id:
                results = [e for e in results if e.workspace_id == workspace_id]
            if trace_id:
                results = [e for e in results if e.trace_id == trace_id]
            if status:
                results = [e for e in results if e.status == status]
            if since:
                results = [e for e in results if e.timestamp >= since]
            if until:
                results = [e for e in results if e.timestamp <= until]

            # Return most recent first, limited
            return sorted(results, key=lambda e: e.timestamp, reverse=True)[:limit]

    def count(
        self,
        event_type: Optional[AuditEventType] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Count matching events."""
        with self._lock:
            results = self.events
            if event_type:
                results = [e for e in results if e.event_type == event_type]
            if status:
                results = [e for e in results if e.status == status]
            if since:
                results = [e for e in results if e.timestamp >= since]
            return len(results)


class FileAuditStore(AuditStore):
    """File-based audit event store (JSONL format).

    Persists events to newline-delimited JSON for durability and forensics.
    Thread-safe using file locks.
    """

    def __init__(self, path: Path):
        """Initialize file store.

        Args:
            path: Path to audit log file (JSONL format)
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def store(self, event: AuditEvent) -> None:
        """Append event to JSONL file."""
        try:
            with self._lock:
                with open(self.path, "a") as f:
                    event_dict = event.to_dict()
                    f.write(json.dumps(event_dict) + "\n")
        except Exception as e:
            # Log but don't raise - audit failure shouldn't break the app
            import logging
            logging.getLogger(__name__).error(f"Failed to store audit event: {e}")

    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[AuditEvent]:
        """Query events from file (full scan)."""
        try:
            results = []
            if not self.path.exists():
                return []

            with self._lock:
                with open(self.path, "r") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            # Reconstruct AuditEvent from dict
                            event = self._dict_to_event(data)
                            if event and self._matches(event, event_type, user_id, workspace_id, trace_id, status, since, until):
                                results.append(event)
                        except Exception:
                            pass  # Skip malformed lines

            # Return most recent first, limited
            return sorted(results, key=lambda e: e.timestamp, reverse=True)[:limit]
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to query audit events: {e}")
            return []

    def count(
        self,
        event_type: Optional[AuditEventType] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Count matching events in file."""
        try:
            count = 0
            if not self.path.exists():
                return 0

            with self._lock:
                with open(self.path, "r") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            event = self._dict_to_event(data)
                            if event and self._matches(event, event_type, None, None, None, status, since, None):
                                count += 1
                        except Exception:
                            pass
            return count
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to count audit events: {e}")
            return 0

    @staticmethod
    def _dict_to_event(data: Dict[str, Any]) -> Optional[AuditEvent]:
        """Reconstruct AuditEvent from dict."""
        try:
            return AuditEvent(
                event_type=AuditEventType(data.get("event_type")),
                timestamp=datetime.fromisoformat(data.get("timestamp", "")),
                trace_id=data.get("trace_id", ""),
                user_id=data.get("user_id"),
                workspace_id=data.get("workspace_id"),
                resource=data.get("resource"),
                action=data.get("action"),
                status=data.get("status", "success"),
                details=data.get("details"),
            )
        except Exception:
            return None

    @staticmethod
    def _matches(
        event: AuditEvent,
        event_type: Optional[AuditEventType],
        user_id: Optional[str],
        workspace_id: Optional[str],
        trace_id: Optional[str],
        status: Optional[str],
        since: Optional[datetime],
        until: Optional[datetime],
    ) -> bool:
        """Check if event matches all filters."""
        if event_type and event.event_type != event_type:
            return False
        if user_id and event.user_id != user_id:
            return False
        if workspace_id and event.workspace_id != workspace_id:
            return False
        if trace_id and event.trace_id != trace_id:
            return False
        if status and event.status != status:
            return False
        if since and event.timestamp < since:
            return False
        if until and event.timestamp > until:
            return False
        return True


def create_audit_store(store_type: str = "memory", path: Optional[Path] = None) -> AuditStore:
    """Factory for audit stores.

    Args:
        store_type: "memory" or "file"
        path: Path for file store (required if type is "file")

    Returns:
        AuditStore instance
    """
    if store_type == "file":
        if path is None:
            # Default path for file store
            path = Path.cwd() / ".audit" / "events.jsonl"
        return FileAuditStore(path)
    else:
        return InMemoryAuditStore()
