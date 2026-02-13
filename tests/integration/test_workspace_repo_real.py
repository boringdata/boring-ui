"""Integration tests for SupabaseWorkspaceRepository against real Supabase.

Bead: bd-1joj.4 (DB1)

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from control_plane.app.db.supabase_client import SupabaseClient
from control_plane.app.db.workspace_repo import SupabaseWorkspaceRepository


def _skip_without_creds():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")
    return url, key


@pytest.mark.asyncio
async def test_real_create_get_update_roundtrip():
    url, key = _skip_without_creds()
    async with httpx.AsyncClient() as http:
        client = SupabaseClient(supabase_url=url, service_role_key=key, http_client=http)
        repo = SupabaseWorkspaceRepository(client)

        owner_id = str(uuid.uuid4())
        ws = await repo.create({"name": "DB1 integration test", "owner_id": owner_id})
        ws_id = ws["id"]
        assert ws_id.startswith("ws_")
        assert ws["app_id"] == "boring-ui"

        # Get
        fetched = await repo.get(ws_id)
        assert fetched is not None
        assert fetched["name"] == "DB1 integration test"

        # Update
        updated = await repo.update(ws_id, {"name": "Updated name"})
        assert updated is not None
        assert updated["name"] == "Updated name"

        # Cleanup
        await client.delete("cloud.workspaces", filters={"id": ("eq", ws_id)})


@pytest.mark.asyncio
async def test_real_list_for_user_respects_membership():
    url, key = _skip_without_creds()
    async with httpx.AsyncClient() as http:
        client = SupabaseClient(supabase_url=url, service_role_key=key, http_client=http)
        repo = SupabaseWorkspaceRepository(client)

        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())

        # Create two workspaces
        ws1 = await repo.create({"name": "User A workspace", "owner_id": user_a})
        ws2 = await repo.create({"name": "User B workspace", "owner_id": user_b})

        # Add active membership for user_a on ws1 only
        await client.insert("cloud.workspace_members", {
            "workspace_id": ws1["id"],
            "user_id": user_a,
            "email": f"{user_a}@test.com",
            "role": "admin",
            "status": "active",
        })

        # Add active membership for user_b on ws2 only
        await client.insert("cloud.workspace_members", {
            "workspace_id": ws2["id"],
            "user_id": user_b,
            "email": f"{user_b}@test.com",
            "role": "admin",
            "status": "active",
        })

        # list_for_user(user_a) should return only ws1
        user_a_workspaces = await repo.list_for_user(user_a)
        user_a_ws_ids = {ws["id"] for ws in user_a_workspaces}
        assert ws1["id"] in user_a_ws_ids
        assert ws2["id"] not in user_a_ws_ids

        # list_for_user(user_b) should return only ws2
        user_b_workspaces = await repo.list_for_user(user_b)
        user_b_ws_ids = {ws["id"] for ws in user_b_workspaces}
        assert ws2["id"] in user_b_ws_ids
        assert ws1["id"] not in user_b_ws_ids

        # Cleanup (cascade deletes members)
        await client.delete("cloud.workspaces", filters={"id": ("eq", ws1["id"])})
        await client.delete("cloud.workspaces", filters={"id": ("eq", ws2["id"])})
