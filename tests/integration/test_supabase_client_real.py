from __future__ import annotations

import os
import uuid

import pytest

from control_plane.app.db.supabase_client import SupabaseClient


@pytest.mark.asyncio
async def test_real_select_against_cloud_workspaces_table():
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not service_role_key:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")

    client = SupabaseClient(supabase_url=supabase_url, service_role_key=service_role_key)
    rows = await client.select("cloud.workspaces", limit=1)
    assert isinstance(rows, list)


@pytest.mark.asyncio
async def test_real_insert_select_delete_roundtrip():
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not service_role_key:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")

    client = SupabaseClient(supabase_url=supabase_url, service_role_key=service_role_key)

    # Assumes MIG0 has applied the schema and table exists.
    ws_id = f"ws_test_{uuid.uuid4().hex[:12]}"
    created = await client.insert(
        "cloud.workspaces",
        {
            "id": ws_id,
            "name": "SupabaseClient integration test",
            "app_id": "boring-ui",
        },
    )
    assert created and created[0].get("id") == ws_id

    fetched = await client.select("cloud.workspaces", filters={"id": ("eq", ws_id)}, limit=1)
    assert fetched and fetched[0].get("id") == ws_id

    deleted = await client.delete("cloud.workspaces", filters={"id": ("eq", ws_id)})
    # PostgREST returns deleted row(s) when Prefer: return=representation is set.
    assert deleted and deleted[0].get("id") == ws_id

