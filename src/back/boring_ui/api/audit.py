"""Audit logging and observability for boring-ui (bd-1pwb.9).

Provides:
- Structured audit logs for all sensitive operations
- Request correlation via trace IDs
- Metrics collection (latency, errors, auth events)
- Operational dashboards (future)
"""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional, Any, Dict
from enum import Enum
from datetime import datetime


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
    """Structured audit event."""

    event_type: AuditEventType
    timestamp: datetime
    trace_id: str
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    status: str = "success"  # success, failure, denied
    details: Dict[str, Any] = None

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


class AuditLogger:
    """Centralized audit logging for security and compliance."""

    def __init__(self):
        self.logger = logging.getLogger("boring_ui.audit")
        self.metrics = AuditMetrics()

    def log_auth_success(
        self, user_id: str, workspace_id: Optional[str] = None, trace_id: Optional[str] = None
    ):
        """Log successful authentication."""
        trace_id = trace_id or str(uuid.uuid4())
        event = AuditEvent(
            event_type=AuditEventType.AUTH_SUCCESS,
            timestamp=datetime.utcnow(),
            trace_id=trace_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        self.logger.info(f"Auth success: {event.to_dict()}")
        self.metrics.record_auth_success()
        return event

    def log_auth_failure(self, reason: str, trace_id: Optional[str] = None):
        """Log failed authentication attempt."""
        trace_id = trace_id or str(uuid.uuid4())
        event = AuditEvent(
            event_type=AuditEventType.AUTH_FAILURE,
            timestamp=datetime.utcnow(),
            trace_id=trace_id,
            status="failure",
            details={"reason": reason},
        )
        self.logger.warning(f"Auth failure: {event.to_dict()}")
        self.metrics.record_auth_failure()
        return event

    def log_file_operation(
        self,
        user_id: str,
        operation: str,  # read, write
        path: str,
        workspace_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ):
        """Log file read/write operations."""
        trace_id = trace_id or str(uuid.uuid4())
        event_type = (
            AuditEventType.FILE_READ if operation == "read" else AuditEventType.FILE_WRITE
        )
        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            trace_id=trace_id,
            user_id=user_id,
            workspace_id=workspace_id,
            resource=path,
            action=operation,
        )
        self.logger.info(f"File operation: {event.to_dict()}")
        self.metrics.record_file_operation(operation)
        return event

    def log_exec_operation(
        self,
        user_id: str,
        command: str,
        workspace_id: Optional[str] = None,
        exit_code: Optional[int] = None,
        trace_id: Optional[str] = None,
    ):
        """Log command execution."""
        trace_id = trace_id or str(uuid.uuid4())
        event = AuditEvent(
            event_type=AuditEventType.EXEC_RUN,
            timestamp=datetime.utcnow(),
            trace_id=trace_id,
            user_id=user_id,
            workspace_id=workspace_id,
            action="execute",
            details={
                "command": command[:100],  # Truncate for security
                "exit_code": exit_code,
            },
        )
        self.logger.info(f"Exec operation: {event.to_dict()}")
        self.metrics.record_exec_operation()
        return event

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
        self.start_time = datetime.utcnow()

    def record_auth_success(self):
        self.auth_success_count += 1

    def record_auth_failure(self):
        self.auth_failure_count += 1

    def record_file_operation(self, operation: str):
        if operation == "read":
            self.file_read_count += 1
        elif operation == "write":
            self.file_write_count += 1

    def record_exec_operation(self):
        self.exec_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Get metrics as dict."""
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
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


# Global audit logger instance
audit_logger = AuditLogger()
