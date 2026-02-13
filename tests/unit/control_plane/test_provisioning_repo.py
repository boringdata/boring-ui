from __future__ import annotations

from typing import Any

import httpx
import pytest

from control_plane.app.db.errors import SupabaseConflictError
from control_plane.app.db.provisioning_repo import (
    ACTIVE_STATES,
    SupabaseProvisioningJobRepository,
)
from control_plane.app.db.supabase_client import SupabaseClient


def _make_client(handler) -> tuple[httpx.AsyncClient, SupabaseClient]:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    client = SupabaseClient(
        supabase_url="https://test.supabase.co",
        service_role_key="test-key",
        http_client=http,
    )
    return http, client


@pytest.mark.asyncio
async def test_create_job_inserts_with_all_fields():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        body = request.content.decode()
        seen["body"] = body
        return httpx.Response(
            201,
            json=[{
                "id": "job_abc123",
                "workspace_id": "ws_1",
                "state": "queued",
                "step": None,
                "attempt": 1,
                "modal_call_id": None,
                "idempotency_key": "idem_1",
                "last_error_code": None,
                "last_error_detail": None,
                "request_id": "req_1",
                "created_by": "user-uuid",
                "started_at": None,
                "finished_at": None,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }],
        )

    http, client = _make_client(handler)
    async with http:
        repo = SupabaseProvisioningJobRepository(client)
        job = await repo.create_job({
            "workspace_id": "ws_1",
            "idempotency_key": "idem_1",
            "created_by": "user-uuid",
            "request_id": "req_1",
        })

    assert job["id"] == "job_abc123"
    assert job["workspace_id"] == "ws_1"
    assert job["state"] == "queued"
    assert job["idempotency_key"] == "idem_1"
    assert seen["method"] == "POST"


@pytest.mark.asyncio
async def test_single_active_job_conflict_raises():
    """Second create for same workspace with active job raises SupabaseConflictError."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={"message": "duplicate key violates unique constraint"},
        )

    http, client = _make_client(handler)
    async with http:
        repo = SupabaseProvisioningJobRepository(client)
        with pytest.raises(SupabaseConflictError):
            await repo.create_job({
                "workspace_id": "ws_1",
            })


@pytest.mark.asyncio
async def test_idempotency_key_dedup_returns_existing_job():
    """Same idempotency key returns existing job instead of raising."""
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Insert fails with 409 (idempotency key conflict)
            return httpx.Response(
                409,
                json={"message": "duplicate key"},
            )
        # Select returns existing job
        return httpx.Response(
            200,
            json=[{
                "id": "job_existing",
                "workspace_id": "ws_1",
                "idempotency_key": "idem_dup",
                "state": "queued",
            }],
        )

    http, client = _make_client(handler)
    async with http:
        repo = SupabaseProvisioningJobRepository(client)
        job = await repo.create_job({
            "workspace_id": "ws_1",
            "idempotency_key": "idem_dup",
        })

    assert job["id"] == "job_existing"
    assert job["idempotency_key"] == "idem_dup"
    assert call_count == 2  # insert + select


@pytest.mark.asyncio
async def test_update_job_state_transitions_correctly():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode())
        seen["body"] = body
        return httpx.Response(
            200,
            json=[{
                "id": "job_1",
                "state": body.get("state", "queued"),
                "step": body.get("step"),
                "last_error_code": body.get("last_error_code"),
                "last_error_detail": body.get("last_error_detail"),
                "updated_at": body.get("updated_at"),
                "started_at": body.get("started_at"),
            }],
        )

    http, client = _make_client(handler)
    async with http:
        repo = SupabaseProvisioningJobRepository(client)
        job = await repo.update_job("job_1", {
            "state": "creating_sandbox",
            "step": "sandbox_create",
        })

    assert job is not None
    assert job["state"] == "creating_sandbox"
    assert job["step"] == "sandbox_create"
    assert "updated_at" in seen["body"]
    # started_at is NOT auto-set (caller must set it explicitly to avoid
    # overwriting on subsequent transitions without read-before-write).
    assert "started_at" not in seen["body"]


@pytest.mark.asyncio
async def test_update_job_sets_finished_at_on_terminal_state():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode())
        seen["body"] = body
        return httpx.Response(200, json=[{"id": "job_1", **body}])

    http, client = _make_client(handler)
    async with http:
        repo = SupabaseProvisioningJobRepository(client)
        await repo.update_job("job_1", {"state": "ready"})

    assert seen["body"].get("finished_at") is not None


@pytest.mark.asyncio
async def test_get_active_job_returns_current_active_or_none():
    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        # Verify state filter uses `in` operator.
        assert "state=in." in url
        return httpx.Response(200, json=[])

    http, client = _make_client(handler)
    async with http:
        repo = SupabaseProvisioningJobRepository(client)
        result = await repo.get_active_job("ws_1")

    assert result is None


@pytest.mark.asyncio
async def test_get_active_job_returns_job_when_active():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"id": "job_active", "workspace_id": "ws_1", "state": "queued"}],
        )

    http, client = _make_client(handler)
    async with http:
        repo = SupabaseProvisioningJobRepository(client)
        result = await repo.get_active_job("ws_1")

    assert result is not None
    assert result["id"] == "job_active"


@pytest.mark.asyncio
async def test_list_jobs_returns_all_for_workspace():
    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert "workspace_id=eq.ws_1" in url
        assert "order=created_at.desc" in url
        return httpx.Response(
            200,
            json=[
                {"id": "job_2", "state": "ready"},
                {"id": "job_1", "state": "error"},
            ],
        )

    http, client = _make_client(handler)
    async with http:
        repo = SupabaseProvisioningJobRepository(client)
        jobs = await repo.list_jobs("ws_1")

    assert len(jobs) == 2
    assert jobs[0]["id"] == "job_2"


@pytest.mark.asyncio
async def test_get_job_returns_none_when_missing():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    http, client = _make_client(handler)
    async with http:
        repo = SupabaseProvisioningJobRepository(client)
        result = await repo.get_job("job_nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_active_states_match_migration_index():
    """Verify ACTIVE_STATES matches the partial index WHERE clause from migration 002."""
    expected = {
        "queued", "release_resolve", "creating_sandbox",
        "uploading_artifact", "bootstrapping", "health_check",
    }
    assert ACTIVE_STATES == expected
