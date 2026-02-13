from __future__ import annotations

import os
import uuid

import httpx
import pytest

from control_plane.app.db.supabase_client import SupabaseClient


def _skip_without_creds():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")
    return url, key


@pytest.mark.asyncio
async def test_real_select_against_cloud_workspaces_table():
    url, key = _skip_without_creds()
    async with httpx.AsyncClient() as http:
        client = SupabaseClient(supabase_url=url, service_role_key=key, http_client=http)
        rows = await client.select("cloud.workspaces", limit=1)
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_real_insert_select_delete_roundtrip():
    url, key = _skip_without_creds()
    async with httpx.AsyncClient() as http:
        client = SupabaseClient(supabase_url=url, service_role_key=key, http_client=http)

        # Assumes MIG0 has applied the schema and table exists.
        ws_id = f"ws_test_{uuid.uuid4().hex[:12]}"
        fake_owner = str(uuid.uuid4())
        created = await client.insert(
            "cloud.workspaces",
            {
                "id": ws_id,
                "name": "SupabaseClient integration test",
                "app_id": "boring-ui",
                "owner_id": fake_owner,
            },
        )
        assert created and created[0].get("id") == ws_id

        fetched = await client.select("cloud.workspaces", filters={"id": ("eq", ws_id)}, limit=1)
        assert fetched and fetched[0].get("id") == ws_id

        deleted = await client.delete("cloud.workspaces", filters={"id": ("eq", ws_id)})
        # PostgREST returns deleted row(s) when Prefer: return=representation is set.
        assert deleted and deleted[0].get("id") == ws_id

