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
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone

# Import audit models (data structures)
from .audit_models import AuditEvent, AuditEventType

# Import persistence implementations (bd-1pwb.9.2)
from .audit_persistence import AuditStore, FileAuditStore, create_audit_store



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

        return self.store.query(
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
