"""Audit logging and observability for boring-ui (bd-1pwb.9).

Provides:
- Structured audit logs for all sensitive operations
- Request correlation via trace IDs
- Metrics collection (latency, errors, auth events)
- Audit event persistence for compliance and forensics (bd-1pwb.9.2)
- Operational dashboards (future)
"""

import logging
import time
import uuid
import json
import threading
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List
from enum import Enum
from datetime import datetime, timezone
from pathlib import Path
from abc import ABC, abstractmethod


class AuditEventType(str, Enum):
    """Types of events to audit."""
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTHZ_DENIED = "authz_denied"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    GIT_COMMIT = "git_commit"
    EXEC_RUN = "exec_run"
    SANDBOX_START = "sandbox_start"
    SANDBOX_STOP = "sandbox_stop"


@dataclass
class AuditEvent:
    """Structured audit event for compliance and forensics (bd-1pwb.9.2)."""

    event_type: AuditEventType
    timestamp: datetime
    trace_id: str
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    status: str = "success"  # success, failure, denied
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "resource": self.resource,
            "action": self.action,
            "status": self.status,
            "details": self.details or {},
        }


class AuditStore(ABC):
    """Abstract base class for audit event persistence (bd-1pwb.9.2)."""

    @abstractmethod
    async def store(self, event: "AuditEvent") -> None:
        """Store an audit event for compliance and forensics.

        Args:
            event: AuditEvent to persist
        """
        pass

    @abstractmethod
    async def query(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List["AuditEvent"]:
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

    async def store(self, event: AuditEvent) -> None:
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

    async def query(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
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


class AuditLogger:
    """Centralized audit logging for security and compliance (bd-1pwb.9.2).

    Provides both structured logging and event persistence for forensics.
    All sensitive operations are recorded for audit trail.
    """

    def __init__(self, store: Optional[AuditStore] = None):
        """Initialize audit logger with optional persistence.

        Args:
            store: Optional AuditStore for event persistence (bd-1pwb.9.2).
                  If None, events are logged but not persisted to audit trail.
        """
        self.logger = logging.getLogger("boring_ui.audit")
        self.metrics = AuditMetrics()
        self.store = store

    def _persist_event(self, event: AuditEvent) -> None:
        """Persist audit event to configured store (bd-1pwb.9.2).

        Non-blocking: uses asyncio.create_task for background persistence.
        Failures are logged but don't crash the application.

        Args:
            event: AuditEvent to persist
        """
        if not self.store:
            return

        try:
            import asyncio
            asyncio.create_task(self.store.store(event))
        except RuntimeError:
            # Outside async context - log but don't crash
            self.logger.debug("Could not persist event (outside async context)")

    def _persist_event(self, event: AuditEvent) -> None:
        """Persist event to storage backend.

        Logs errors but doesn't raise - audit failure shouldn't break the app.

        Args:
            event: AuditEvent to persist
        """
        if self.store:
            try:
                self.store.store(event)
            except Exception as e:
                self.logger.error(f"Failed to persist audit event: {e}")

    def log_auth_success(
        self, user_id: str, workspace_id: Optional[str] = None, trace_id: Optional[str] = None, request_id: Optional[str] = None
    ):
        """Log successful authentication (bd-1pwb.9.2).

        Args:
            user_id: Authenticated user ID
            workspace_id: Optional workspace context
            trace_id: Optional trace ID for correlation (deprecated - use request_id)
            request_id: Request correlation ID from request.state.request_id (bd-1pwb.9.1)
        """
        trace_id = trace_id or request_id or str(uuid.uuid4())
        event = AuditEvent(
            event_type=AuditEventType.AUTH_SUCCESS,
            timestamp=datetime.now(timezone.utc),
            trace_id=trace_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )

        # Log with structured fields including request_id
        log_record = self.logger.makeRecord(
            name=self.logger.name,
            level=logging.INFO,
            fn=__file__,
            lno=0,
            msg=f"Auth success: {user_id}",
            args=(),
            exc_info=None,
        )
        log_record.request_id = trace_id
        log_record.user_id = user_id
        if workspace_id:
            log_record.workspace_id = workspace_id
        self.logger.handle(log_record)

        # Persist to storage backend
        self._persist_event(event)

        self.metrics.record_auth_success()
        return event

    def log_auth_failure(self, reason: str, trace_id: Optional[str] = None, request_id: Optional[str] = None):
        """Log failed authentication attempt.

        Args:
            reason: Reason for failure
            trace_id: Optional trace ID for correlation (deprecated - use request_id)
            request_id: Request correlation ID from request.state.request_id (bd-1pwb.9.1)
        """
        trace_id = trace_id or request_id or str(uuid.uuid4())
        event = AuditEvent(
            event_type=AuditEventType.AUTH_FAILURE,
            timestamp=datetime.now(timezone.utc),
            trace_id=trace_id,
            status="failure",
            details={"reason": reason},
        )

        # Log with structured fields including request_id
        log_record = self.logger.makeRecord(
            name=self.logger.name,
            level=logging.WARNING,
            fn=__file__,
            lno=0,
            msg=f"Auth failure: {reason}",
            args=(),
            exc_info=None,
        )
        log_record.request_id = trace_id
        self.logger.handle(log_record)

        # Persist event for compliance audit trail (bd-1pwb.9.2)
        self._persist_event(event)

        self.metrics.record_auth_failure()
        return event

    def log_authz_denied(
        self,
        user_id: str,
        resource: str,
        action: str,
        workspace_id: Optional[str] = None,
        reason: Optional[str] = None,
        trace_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """Log authorization denial (policy rejection).

        Critical for security investigation - denials are as important as
        successes for identifying abuse attempts and policy violations.

        Args:
            user_id: User whose request was denied
            resource: Resource being accessed
            action: Action attempted
            workspace_id: Optional workspace context
            reason: Reason for denial (e.g., "missing_permission", "quota_exceeded")
            trace_id: Optional trace ID for correlation (deprecated - use request_id)
            request_id: Request correlation ID from request.state.request_id (bd-1pwb.9.1)
        """
        trace_id = trace_id or request_id or str(uuid.uuid4())
        event = AuditEvent(
            event_type=AuditEventType.AUTHZ_DENIED,
            timestamp=datetime.now(timezone.utc),
            trace_id=trace_id,
            user_id=user_id,
            workspace_id=workspace_id,
            resource=resource,
            action=action,
            status="denied",
            details={"reason": reason} if reason else {},
        )

        # Log with structured fields
        log_record = self.logger.makeRecord(
            name=self.logger.name,
            level=logging.WARNING,
            fn=__file__,
            lno=0,
            msg=f"Authz denied: {user_id} {action} {resource}",
            args=(),
            exc_info=None,
        )
        log_record.request_id = trace_id
        log_record.user_id = user_id
        if workspace_id:
            log_record.workspace_id = workspace_id
        self.logger.handle(log_record)

        # Persist event for compliance audit trail (bd-1pwb.9.2)
        self._persist_event(event)

        return event

    def log_file_operation(
        self,
        user_id: str,
        operation: str,  # read, write
        path: str,
        workspace_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """Log file read/write operations.

        Args:
            user_id: User performing operation
            operation: 'read' or 'write'
            path: File path
            workspace_id: Optional workspace context
            trace_id: Optional trace ID for correlation (deprecated - use request_id)
            request_id: Request correlation ID from request.state.request_id (bd-1pwb.9.1)
        """
        trace_id = trace_id or request_id or str(uuid.uuid4())

        # Normalize and validate operation
        op_normalized = operation.lower().strip()
        if op_normalized not in ("read", "write"):
            raise ValueError(f"Invalid file operation: {operation}. Must be 'read' or 'write'.")

        event_type = (
            AuditEventType.FILE_READ if op_normalized == "read" else AuditEventType.FILE_WRITE
        )
        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            trace_id=trace_id,
            user_id=user_id,
            workspace_id=workspace_id,
            resource=path,
            action=op_normalized,
        )

        # Log with structured fields
        log_record = self.logger.makeRecord(
            name=self.logger.name,
            level=logging.INFO,
            fn=__file__,
            lno=0,
            msg=f"File {op_normalized}: {path}",
            args=(),
            exc_info=None,
        )
        log_record.request_id = trace_id
        log_record.user_id = user_id
        if workspace_id:
            log_record.workspace_id = workspace_id
        self.logger.handle(log_record)

        # Persist event for compliance audit trail (bd-1pwb.9.2)
        self._persist_event(event)

        self.metrics.record_file_operation(op_normalized)
        return event

    def log_exec_operation(
        self,
        user_id: str,
        command: str,
        workspace_id: Optional[str] = None,
        exit_code: Optional[int] = None,
        trace_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """Log command execution.

        Args:
            user_id: User executing command
            command: Command executed
            workspace_id: Optional workspace context
            exit_code: Optional exit code
            trace_id: Optional trace ID for correlation (deprecated - use request_id)
            request_id: Request correlation ID from request.state.request_id (bd-1pwb.9.1)
        """
        trace_id = trace_id or request_id or str(uuid.uuid4())
        event = AuditEvent(
            event_type=AuditEventType.EXEC_RUN,
            timestamp=datetime.now(timezone.utc),
            trace_id=trace_id,
            user_id=user_id,
            workspace_id=workspace_id,
            action="execute",
            details={
                "command": command[:100],  # Truncate for security
                "exit_code": exit_code,
            },
        )

        # Log with structured fields
        log_record = self.logger.makeRecord(
            name=self.logger.name,
            level=logging.INFO,
            fn=__file__,
            lno=0,
            msg=f"Exec: {command[:50]}",
            args=(),
            exc_info=None,
        )
        log_record.request_id = trace_id
        log_record.user_id = user_id
        if workspace_id:
            log_record.workspace_id = workspace_id
        self.logger.handle(log_record)

        # Persist event for compliance audit trail (bd-1pwb.9.2)
        self._persist_event(event)

        self.metrics.record_exec_operation()
        return event

    async def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Query audit events for forensics and compliance review (bd-1pwb.9.2).

        Supports filtering by event type, user, workspace, and time range.
        Returns most recent events first.

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
        if not self.store:
            return []

        return await self.store.query(
            event_type=event_type,
            user_id=user_id,
            workspace_id=workspace_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get observability metrics."""
        return self.metrics.to_dict()


class AuditMetrics:
    """Observability metrics for operations."""

    def __init__(self):
        self.auth_success_count = 0
        self.auth_failure_count = 0
        self.file_read_count = 0
        self.file_write_count = 0
        self.exec_count = 0
        self.start_time = datetime.now(timezone.utc)

    def record_auth_success(self):
        self.auth_success_count += 1

    def record_auth_failure(self):
        self.auth_failure_count += 1

    def record_file_operation(self, operation: str):
        op = operation.lower().strip()
        if op == "read":
            self.file_read_count += 1
        elif op == "write":
            self.file_write_count += 1
        # Ignore unknown operations

    def record_exec_operation(self):
        self.exec_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Get metrics as dict."""
        uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return {
            "uptime_seconds": uptime_seconds,
            "auth_success": self.auth_success_count,
            "auth_failure": self.auth_failure_count,
            "file_operations": {
                "read": self.file_read_count,
                "write": self.file_write_count,
            },
            "exec_operations": self.exec_count,
            "total_operations": (
                self.auth_success_count
                + self.auth_failure_count
                + self.file_read_count
                + self.file_write_count
                + self.exec_count
            ),
        }


# Global audit logger instance with file-based persistence (bd-1pwb.9.2)
_audit_store = FileAuditStore()
audit_logger = AuditLogger(store=_audit_store)
