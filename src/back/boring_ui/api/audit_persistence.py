"""Audit event persistence implementations (bd-1pwb.9.2).

Provides pluggable storage backends for audit logs:
- InMemoryAuditStore: Fast, in-memory (suitable for testing)
- FileAuditStore: JSONL file (suitable for production audit trails)
"""

import json
import logging
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from .audit_models import AuditEvent, AuditEventType


class AuditStore(ABC):
    """Abstract base class for audit event persistence (bd-1pwb.9.2)."""

    @abstractmethod
    def store(self, event: AuditEvent) -> None:
        """Store an audit event for compliance and forensics.

        Args:
            event: AuditEvent to persist
        """
        pass

    @abstractmethod
    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit events for compliance review and forensics.

        Args:
            event_type: Optional event type filter
            user_id: Optional user ID filter
            workspace_id: Optional workspace ID filter
            start_time: Optional start time for range query
            end_time: Optional end time for range query
            limit: Maximum results to return

        Returns:
            List of AuditEvent matching filters
        """
        pass


class InMemoryAuditStore(AuditStore):
    """In-memory audit store for testing and development (bd-1pwb.9.2).

    Fast, no I/O overhead. Events are lost on restart.
    Suitable for testing and development only.
    """

    def __init__(self):
        """Initialize in-memory store."""
        self.events: List[AuditEvent] = []
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def store(self, event: AuditEvent) -> None:
        """Store event in memory.

        Args:
            event: AuditEvent to store
        """
        with self._lock:
            self.events.append(event)

    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query events from memory.

        Args:
            event_type: Optional event type filter
            user_id: Optional user ID filter
            workspace_id: Optional workspace ID filter
            status: Optional status filter (success, failure, denied)
            start_time: Optional start time for range query
            end_time: Optional end time for range query
            limit: Maximum results to return

        Returns:
            List of AuditEvent matching filters (most recent first)
        """
        with self._lock:
            results = []
            for event in self.events:
                # Apply filters
                if event_type and event.event_type != event_type:
                    continue
                if user_id and event.user_id != user_id:
                    continue
                if workspace_id and event.workspace_id != workspace_id:
                    continue
                if status and event.status != status:
                    continue
                if start_time and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp > end_time:
                    continue

                results.append(event)

        # Return most recent events (reverse chronological)
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]


class FileAuditStore(AuditStore):
    """File-based audit event persistence using JSONL format (bd-1pwb.9.2).

    Stores audit events in a JSONL file (one JSON object per line) for:
    - Compliance auditing (immutable audit trail)
    - Security forensics (investigation of incidents)
    - Incident response (tracing user actions during breach)

    Thread-safe file operations for concurrent access.
    """

    def __init__(self, logs_dir: Optional[Path] = None):
        """Initialize file-based audit store.

        Args:
            logs_dir: Directory to store audit logs. Defaults to .logs/audit
        """
        self.logs_dir = logs_dir or Path.cwd() / ".logs" / "audit"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.logs_dir / "events.jsonl"
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def store(self, event: AuditEvent) -> None:
        """Store audit event to JSONL file.

        Appends event as a single JSON line. Thread-safe.

        Args:
            event: AuditEvent to store
        """
        try:
            with self._lock:
                with open(self.audit_file, "a") as f:
                    json.dump(event.to_dict(), f)
                    f.write("\n")
        except Exception as e:
            # Log error but don't crash the application
            self.logger.error(f"Failed to store audit event: {e}", exc_info=True)

    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit events from JSONL file.

        Filters events based on provided criteria. Thread-safe.

        Args:
            event_type: Optional event type filter
            user_id: Optional user ID filter
            workspace_id: Optional workspace ID filter
            status: Optional status filter (success, failure, denied)
            start_time: Optional start time for range query
            end_time: Optional end time for range query
            limit: Maximum results to return

        Returns:
            List of AuditEvent matching filters (limited to most recent)
        """
        if not self.audit_file.exists():
            return []

        events = []
        try:
            with self._lock:
                with open(self.audit_file, "r") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            event = self._from_dict(data)

                            # Apply filters
                            if event_type and event.event_type != event_type:
                                continue
                            if user_id and event.user_id != user_id:
                                continue
                            if workspace_id and event.workspace_id != workspace_id:
                                continue
                            if status and event.status != status:
                                continue
                            if start_time and event.timestamp < start_time:
                                continue
                            if end_time and event.timestamp > end_time:
                                continue

                            events.append(event)
                        except (json.JSONDecodeError, ValueError):
                            # Skip malformed lines
                            continue

            # Return most recent events (reverse chronological)
            events.sort(key=lambda e: e.timestamp, reverse=True)
            return events[:limit]
        except Exception as e:
            self.logger.error(f"Failed to query audit events: {e}", exc_info=True)
            return []

    @staticmethod
    def _from_dict(data: Dict[str, Any]) -> AuditEvent:
        """Reconstruct AuditEvent from dictionary.

        Args:
            data: Dictionary from JSON

        Returns:
            Reconstructed AuditEvent
        """
        return AuditEvent(
            event_type=AuditEventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            trace_id=data["trace_id"],
            user_id=data.get("user_id"),
            workspace_id=data.get("workspace_id"),
            resource=data.get("resource"),
            action=data.get("action"),
            status=data.get("status", "success"),
            details=data.get("details", {}),
        )


def create_audit_store(store_type: str = "file", **kwargs) -> AuditStore:
    """Factory function to create audit store instances (bd-1pwb.9.2).

    Args:
        store_type: Type of store ('memory' or 'file')
        **kwargs: Additional arguments for store initialization

    Returns:
        Configured AuditStore instance
    """
    if store_type == "memory":
        return InMemoryAuditStore()
    elif store_type == "file":
        return FileAuditStore(logs_dir=kwargs.get("logs_dir"))
    else:
        raise ValueError(f"Unknown store type: {store_type}")
