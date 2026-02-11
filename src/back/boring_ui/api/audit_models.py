"""Audit event data models (bd-1pwb.9.2).

Defines the core audit event types and data structures.
Separated to avoid circular imports between audit and audit_persistence modules.
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from enum import Enum
from datetime import datetime, timezone


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
