"""Integration tests for SupabaseProvisioningJobRepository against real Supabase.

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars.
Skipped when not set (CI-safe).
"""

from __future__ import annotations

import os
import uuid

import pytest

from control_plane.app.db.errors import SupabaseConflictError
from control_plane.app.db.provisioning_repo import SupabaseProvisioningJobRepository
from control_plane.app.db.supabase_client import SupabaseClient


def _get_client() -> SupabaseClient | None:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return None
    return SupabaseClient(supabase_url=url, service_role_key=key)


@pytest.mark.asyncio
async def test_real_create_job_and_update_state_roundtrip():
    client = _get_client()
    if client is None:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")

    repo = SupabaseProvisioningJobRepository(client)

    # Need a workspace — create one first.
    ws_id = f"ws_test_{uuid.uuid4().hex[:12]}"
    await client.insert("cloud.workspaces", {
        "id": ws_id,
        "name": "provisioning repo integration test",
        "app_id": "boring-ui",
        "owner_id": "00000000-0000-0000-0000-000000000001",
    })

    try:
        idem_key = f"idem_{uuid.uuid4().hex[:8]}"
        job = await repo.create_job({
            "workspace_id": ws_id,
            "idempotency_key": idem_key,
            "created_by": "00000000-0000-0000-0000-000000000001",
        })
        assert job["workspace_id"] == ws_id
        assert job["state"] == "queued"
        job_id = job["id"]

        # Update state.
        updated = await repo.update_job(job_id, {
            "state": "creating_sandbox",
            "step": "sandbox_create",
        })
        assert updated is not None
        assert updated["state"] == "creating_sandbox"

        # Move to terminal.
        finished = await repo.update_job(job_id, {"state": "ready"})
        assert finished is not None
        assert finished["state"] == "ready"
        assert finished.get("finished_at") is not None

        # No active job after terminal.
        active = await repo.get_active_job(ws_id)
        assert active is None

    finally:
        # Cleanup: delete job then workspace.
        await client.delete("cloud.workspace_provision_jobs", {"workspace_id": ("eq", ws_id)})
        await client.delete("cloud.workspaces", {"id": ("eq", ws_id)})


@pytest.mark.asyncio
async def test_real_unique_partial_index_prevents_two_active_jobs():
    client = _get_client()
    if client is None:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")

    repo = SupabaseProvisioningJobRepository(client)

    ws_id = f"ws_test_{uuid.uuid4().hex[:12]}"
    await client.insert("cloud.workspaces", {
        "id": ws_id,
        "name": "unique index test",
        "app_id": "boring-ui",
        "owner_id": "00000000-0000-0000-0000-000000000001",
    })

    try:
        await repo.create_job({"workspace_id": ws_id})

        with pytest.raises(SupabaseConflictError):
            await repo.create_job({"workspace_id": ws_id})

    finally:
        await client.delete("cloud.workspace_provision_jobs", {"workspace_id": ("eq", ws_id)})
        await client.delete("cloud.workspaces", {"id": ("eq", ws_id)})


@pytest.mark.asyncio
async def test_real_idempotency_key_unique_index():
    client = _get_client()
    if client is None:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")

    repo = SupabaseProvisioningJobRepository(client)

    ws_id = f"ws_test_{uuid.uuid4().hex[:12]}"
    await client.insert("cloud.workspaces", {
        "id": ws_id,
        "name": "idempotency test",
        "app_id": "boring-ui",
        "owner_id": "00000000-0000-0000-0000-000000000001",
    })

    try:
        idem_key = f"idem_{uuid.uuid4().hex[:8]}"
        job1 = await repo.create_job({
            "workspace_id": ws_id,
            "idempotency_key": idem_key,
        })

        # Move first job to terminal so single-active-job allows a new one.
        await repo.update_job(job1["id"], {"state": "ready"})

        # Same idempotency key should return the existing job.
        job2 = await repo.create_job({
            "workspace_id": ws_id,
            "idempotency_key": idem_key,
        })
        assert job2["id"] == job1["id"]

    finally:
        await client.delete("cloud.workspace_provision_jobs", {"workspace_id": ("eq", ws_id)})
        await client.delete("cloud.workspaces", {"id": ("eq", ws_id)})
