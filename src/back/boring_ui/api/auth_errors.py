"""Standardized error responses and telemetry for hosted auth.

Provides machine-readable error codes, consistent HTTP semantics,
and telemetry hooks for authentication and authorization events.
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class AuthErrorCode(str, Enum):
    """Machine-readable codes for authentication failures."""

    # 401 Unauthorized: Missing or invalid credentials
    AUTH_MISSING = "AUTH_MISSING"  # No token provided
    AUTH_INVALID = "AUTH_INVALID"  # Token is malformed/invalid
    AUTH_EXPIRED = "AUTH_EXPIRED"  # Token is expired
    AUTH_INVALID_CLAIMS = "AUTH_INVALID_CLAIMS"  # Missing required claims

    # 403 Forbidden: Valid credentials, insufficient permissions
    PERM_DENIED = "PERM_DENIED"  # Missing specific permission
    PERM_INSUFFICIENT = "PERM_INSUFFICIENT"  # Not enough permissions for operation


class AuthEventType(str, Enum):
    """Telemetry events for authentication/authorization."""

    AUTH_ATTEMPT = "auth_attempt"  # Token validation attempted
    AUTH_SUCCESS = "auth_success"  # Token validation succeeded
    AUTH_FAILURE = "auth_failure"  # Token validation failed
    AUTH_EXPIRED = "auth_expired"  # Token was expired
    PERM_CHECK = "perm_check"  # Permission check performed
    PERM_GRANTED = "perm_granted"  # Permission granted
    PERM_DENIED = "perm_denied"  # Permission denied


@dataclass
class AuthErrorResponse:
    """Structured error response for authentication failures."""

    status_code: int
    code: AuthErrorCode
    detail: str
    headers: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "detail": self.detail,
            "code": self.code.value,
        }


class AuthEventLogger:
    """Telemetry for authentication and authorization events."""

    def __init__(self) -> None:
        self._event_counts: dict[AuthEventType, int] = {t: 0 for t in AuthEventType}

    def log_auth_attempt(self, user_id: str | None = None, issuer: str | None = None) -> None:
        """Log authentication attempt."""
        self._event_counts[AuthEventType.AUTH_ATTEMPT] += 1
        logger.info(f"Auth attempt: user={user_id}, issuer={issuer}")

    def log_auth_success(self, user_id: str, workspace_id: str | None = None, permissions: int = 0) -> None:
        """Log successful authentication."""
        self._event_counts[AuthEventType.AUTH_SUCCESS] += 1
        logger.info(
            f"Auth success: user={user_id}, workspace={workspace_id}, "
            f"permissions={permissions}, success_rate={self.success_rate():.1%}"
        )

    def log_auth_failure(self, reason: str) -> None:
        """Log authentication failure (non-sensitive details only)."""
        self._event_counts[AuthEventType.AUTH_FAILURE] += 1
        logger.warning(f"Auth failure: {reason}")

    def log_auth_expired(self) -> None:
        """Log expired token."""
        self._event_counts[AuthEventType.AUTH_EXPIRED] += 1
        logger.debug("Token expired")

    def log_perm_check(self, user_id: str, permission: str) -> None:
        """Log permission check."""
        self._event_counts[AuthEventType.PERM_CHECK] += 1
        logger.debug(f"Permission check: user={user_id}, perm={permission}")

    def log_perm_granted(self, user_id: str, permission: str) -> None:
        """Log granted permission."""
        self._event_counts[AuthEventType.PERM_GRANTED] += 1
        logger.debug(f"Permission granted: user={user_id}, perm={permission}")

    def log_perm_denied(self, user_id: str, permission: str, have: set[str]) -> None:
        """Log denied permission (non-sensitive: just count denied perms)."""
        self._event_counts[AuthEventType.PERM_DENIED] += 1
        logger.warning(
            f"Permission denied: user={user_id}, required={permission}, "
            f"have={len(have)} permissions, denial_rate={self.denial_rate():.1%}"
        )

    def success_rate(self) -> float:
        """Return success rate of auth attempts."""
        total = self._event_counts[AuthEventType.AUTH_ATTEMPT]
        if total == 0:
            return 0.0
        success = self._event_counts[AuthEventType.AUTH_SUCCESS]
        return success / total

    def denial_rate(self) -> float:
        """Return rate of permission denials."""
        checks = self._event_counts[AuthEventType.PERM_CHECK]
        if checks == 0:
            return 0.0
        denials = self._event_counts[AuthEventType.PERM_DENIED]
        return denials / checks

    def get_stats(self) -> dict[str, Any]:
        """Return telemetry statistics."""
        return {
            "events": {t.value: count for t, count in self._event_counts.items()},
            "success_rate": self.success_rate(),
            "denial_rate": self.denial_rate(),
            "total_attempts": self._event_counts[AuthEventType.AUTH_ATTEMPT],
        }


# Global event logger
_event_logger = AuthEventLogger()


def get_event_logger() -> AuthEventLogger:
    """Get the global event logger."""
    return _event_logger


def auth_missing_error() -> AuthErrorResponse:
    """Missing authorization header."""
    return AuthErrorResponse(
        status_code=401,
        code=AuthErrorCode.AUTH_MISSING,
        detail="Missing or invalid Authorization header",
        headers={"WWW-Authenticate": 'Bearer realm="boring-ui"'},
    )


def auth_invalid_error() -> AuthErrorResponse:
    """Invalid or malformed token."""
    return AuthErrorResponse(
        status_code=401,
        code=AuthErrorCode.AUTH_INVALID,
        detail="Invalid or malformed token",
        headers={"WWW-Authenticate": 'Bearer realm="boring-ui", error="invalid_token"'},
    )


def auth_expired_error() -> AuthErrorResponse:
    """Token has expired."""
    return AuthErrorResponse(
        status_code=401,
        code=AuthErrorCode.AUTH_EXPIRED,
        detail="Token has expired",
        headers={"WWW-Authenticate": 'Bearer realm="boring-ui", error="invalid_token"'},
    )


def auth_invalid_claims_error() -> AuthErrorResponse:
    """Token missing required claims."""
    return AuthErrorResponse(
        status_code=401,
        code=AuthErrorCode.AUTH_INVALID_CLAIMS,
        detail="Token missing required claims (sub, aud, iss)",
    )


def permission_denied_error(permission: str) -> AuthErrorResponse:
    """Permission denied for operation."""
    return AuthErrorResponse(
        status_code=403,
        code=AuthErrorCode.PERM_DENIED,
        detail=f"Permission denied: {permission}",
        headers={"X-Permission-Code": f"PERM_DENIED:{permission}"},
    )
