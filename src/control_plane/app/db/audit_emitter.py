"""Supabase-backed AuditEmitter implementation.

Bead: bd-1joj.8 (DB5)

Writes audit events to cloud.audit_events via PostgREST. Emit is
fire-and-forget: DB errors are logged but never propagate to callers.

Credential sanitization: Sprite bearer tokens and service role keys
are stripped from payloads before persistence (section 18.8).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

# Keys that must never appear in audit payloads.
_SENSITIVE_KEYS = frozenset({
    "authorization",
    "apikey",
    "service_role_key",
    "supabase_service_role_key",
    "sprite_bearer_token",
    "bearer_token",
    "token",
    "secret",
    "password",
    "api_key",
})


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Deep-copy payload with sensitive keys redacted."""
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in _SENSITIVE_KEYS:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_payload(value)
        else:
            sanitized[key] = value
    return sanitized


class SupabaseAuditEmitter:
    """AuditEmitter backed by cloud.audit_events via PostgREST.

    emit() is fire-and-forget: errors are logged but never raised.
    """

    TABLE = "cloud.audit_events"

    def __init__(self, client: SupabaseClient) -> None:
        self._client = client

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Write an audit event. Non-blocking: errors are logged, not raised."""
        try:
            row = {
                "action": event_type,
                "workspace_id": data.get("workspace_id", ""),
                "user_id": data.get("user_id"),  # nullable for system
                "request_id": data.get("request_id"),
                "payload": _sanitize_payload(
                    data.get("payload", {}) if isinstance(data.get("payload"), dict) else {}
                ),
            }
            await self._client.insert(self.TABLE, row)
        except Exception:
            logger.exception(
                "Audit emit failed for action=%s workspace=%s",
                event_type,
                data.get("workspace_id", "?"),
            )
