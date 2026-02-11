"""Authentication error models and telemetry for hosted mode.

Provides:
- Standardized error response contract (code, message, request_id)
- Telemetry counters for auth failures
- Strict 401 vs 403 distinction
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


@dataclass
class AuthErrorTelemetry:
    """Telemetry counters for auth failures."""

    authn_missing: int = 0  # 401: Missing/invalid token
    authn_invalid: int = 0  # 401: Token validation failure
    authz_insufficient: int = 0  # 403: Valid token but insufficient permissions


class AuthErrorEmitter:
    """Emits standardized auth error responses with telemetry."""

    def __init__(self):
        self.telemetry = AuthErrorTelemetry()

    def missing_token(self, request_path: str) -> JSONResponse:
        """Emit 401 for missing/invalid authorization header."""
        self.telemetry.authn_missing += 1
        request_id = str(uuid.uuid4())
        logger.debug(f"[{request_id}] Missing Bearer token: {request_path}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "code": "AUTH_MISSING",
                "message": "Missing or invalid authorization header",
                "request_id": request_id,
            },
            headers={"WWW-Authenticate": 'Bearer realm="boring-ui"'},
        )

    def invalid_token(self, request_path: str, reason: str = "Invalid or expired token") -> JSONResponse:
        """Emit 401 for token validation failure."""
        self.telemetry.authn_invalid += 1
        request_id = str(uuid.uuid4())
        logger.debug(f"[{request_id}] Invalid JWT: {request_path} ({reason})")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "code": "AUTH_INVALID",
                "message": reason,
                "request_id": request_id,
            },
            headers={"WWW-Authenticate": 'Bearer realm="boring-ui", error="invalid_token"'},
        )

    def insufficient_permission(
        self, request_path: str, user_id: str, required: str, have: set[str]
    ) -> JSONResponse:
        """Emit 403 for insufficient permissions."""
        self.telemetry.authz_insufficient += 1
        request_id = str(uuid.uuid4())
        logger.warning(
            f"[{request_id}] Permission denied: user={user_id}, "
            f"required={required}, have={have}, path={request_path}"
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "code": "AUTHZ_INSUFFICIENT",
                "message": f"Permission denied: {required}",
                "request_id": request_id,
                "required_permission": required,
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """Get current telemetry stats."""
        total = (
            self.telemetry.authn_missing
            + self.telemetry.authn_invalid
            + self.telemetry.authz_insufficient
        )
        return {
            "total_failures": total,
            "authn_missing": self.telemetry.authn_missing,
            "authn_invalid": self.telemetry.authn_invalid,
            "authz_insufficient": self.telemetry.authz_insufficient,
        }
