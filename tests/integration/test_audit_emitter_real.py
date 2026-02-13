"""Integration test for SupabaseAuditEmitter against real Supabase.

Bead: bd-1joj.8 (DB5)
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from control_plane.app.db.supabase_client import SupabaseClient
from control_plane.app.db.audit_emitter import SupabaseAuditEmitter


def _skip_without_creds():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")
    return url, key


@pytest.mark.asyncio
async def test_real_emit_and_read_back():
    url, key = _skip_without_creds()
    async with httpx.AsyncClient() as http:
        client = SupabaseClient(supabase_url=url, service_role_key=key, http_client=http)
        emitter = SupabaseAuditEmitter(client)

        # Need a workspace for FK (audit_events.workspace_id references workspaces.id... actually not a FK)
        # audit_events.workspace_id is just text, no FK constraint, so we can use any string
        req_id = f"req-{uuid.uuid4().hex[:8]}"
        await emitter.emit("test.integration", {
            "workspace_id": "ws_inttest",
            "user_id": str(uuid.uuid4()),
            "request_id": req_id,
            "payload": {"test": True, "token": "should-be-redacted"},
        })

        # Read back the event
        rows = await client.select(
            "cloud.audit_events",
            filters={
                "request_id": ("eq", req_id),
                "action": ("eq", "test.integration"),
            },
            limit=1,
        )
        assert len(rows) == 1
        event = rows[0]
        assert event["action"] == "test.integration"
        assert event["request_id"] == req_id
        assert event["payload"]["test"] is True
        assert event["payload"]["token"] == "[REDACTED]"

        # Cleanup
        await client.delete("cloud.audit_events", filters={"request_id": ("eq", req_id)})
