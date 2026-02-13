"""Integration test for SupabaseShareLinkRepository against real Supabase.

Bead: bd-1joj.7 (DB4)
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from control_plane.app.db.supabase_client import SupabaseClient
from control_plane.app.db.share_repo import SupabaseShareLinkRepository


def _skip_without_creds():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")
    return url, key


@pytest.mark.asyncio
async def test_real_create_get_revoke_roundtrip():
    url, key = _skip_without_creds()
    async with httpx.AsyncClient() as http:
        client = SupabaseClient(supabase_url=url, service_role_key=key, http_client=http)
        repo = SupabaseShareLinkRepository(client)

        # Create workspace for FK
        owner_id = str(uuid.uuid4())
        ws = await client.insert("cloud.workspaces", {
            "name": "DB4 share test",
            "owner_id": owner_id,
        })
        ws_id = ws[0]["id"]

        try:
            # 1. Create share link
            share = await repo.create_share({
                "workspace_id": ws_id,
                "path": "/docs/readme.md",
                "access": "read",
                "created_by": owner_id,
            })
            assert "token" in share
            assert share["id"].startswith("shr_")
            plaintext_token = share["token"]

            # 2. Get by token
            fetched = await repo.get_share(plaintext_token)
            assert fetched is not None
            assert fetched["path"] == "/docs/readme.md"
            assert fetched["access"] == "read"
            # Plaintext token should NOT be in the DB row
            assert "token" not in fetched or fetched.get("token") != plaintext_token

            # 3. List shares
            shares = await repo.list_shares(ws_id)
            assert any(s["id"] == share["id"] for s in shares)

            # 4. Revoke
            revoked = await repo.delete_share(share["id"])
            assert revoked is True

            # 5. Get after revoke - still returns (with revoked_at set)
            after_revoke = await repo.get_share(plaintext_token)
            assert after_revoke is not None
            assert after_revoke["revoked_at"] is not None

        finally:
            await client.delete("cloud.workspaces", filters={"id": ("eq", ws_id)})
