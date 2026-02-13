from __future__ import annotations

from typing import Any

import httpx
import pytest

from control_plane.app.db.errors import (
    SupabaseAuthError,
    SupabaseConflictError,
    SupabaseNotFoundError,
)
from control_plane.app.db.supabase_client import (
    SupabaseClient,
    _reset_shared_async_client_for_tests,
)


@pytest.mark.asyncio
async def test_select_with_filters_builds_correct_postgrest_query():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json=[{"id": "ws_123"}],
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SupabaseClient(
            supabase_url="https://example.supabase.co",
            service_role_key="svc-key",
            http_client=http_client,
        )
        rows = await client.select(
            "cloud.workspaces",
            filters={
                "id": ("eq", "ws_123"),
                "app_id": ("eq", "boring-ui"),
            },
            limit=1,
        )

    assert rows == [{"id": "ws_123"}]
    assert seen["method"] == "GET"
    # Table name should NOT include schema in the path; schema uses profile headers.
    assert seen["url"].startswith("https://example.supabase.co/rest/v1/workspaces?")
    assert "id=eq.ws_123" in seen["url"]
    assert "app_id=eq.boring-ui" in seen["url"]
    assert "limit=1" in seen["url"]
    assert seen["headers"]["accept-profile"] == "cloud"


@pytest.mark.asyncio
async def test_insert_returns_created_row_and_sends_prefer_representation():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        return httpx.Response(201, json=[{"id": "ws_1", "name": "Acme"}])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SupabaseClient(
            supabase_url="https://example.supabase.co",
            service_role_key="svc-key",
            http_client=http_client,
        )
        rows = await client.insert("cloud.workspaces", {"name": "Acme"})

    assert rows == [{"id": "ws_1", "name": "Acme"}]
    assert "return=representation" in seen["headers"]["prefer"]


@pytest.mark.asyncio
async def test_update_builds_correct_patch_request_and_sends_prefer_representation():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json=[{"id": "ws_123", "name": "New"}])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SupabaseClient(
            supabase_url="https://example.supabase.co",
            service_role_key="svc-key",
            http_client=http_client,
        )
        rows = await client.update(
            "cloud.workspaces",
            filters={"id": ("eq", "ws_123")},
            data={"name": "New"},
        )

    assert rows == [{"id": "ws_123", "name": "New"}]
    assert seen["method"] == "PATCH"
    assert "id=eq.ws_123" in seen["url"]
    assert "return=representation" in seen["headers"]["prefer"]


@pytest.mark.asyncio
async def test_401_raises_supabase_auth_error_and_does_not_leak_service_role_key():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SupabaseClient(
            supabase_url="https://example.supabase.co",
            service_role_key="TOPSECRET",
            http_client=http_client,
        )
        with pytest.raises(SupabaseAuthError) as exc:
            await client.select("cloud.workspaces")

    # Error message should not include the key.
    assert "TOPSECRET" not in str(exc.value)


@pytest.mark.asyncio
async def test_404_raises_supabase_not_found_error():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SupabaseClient(
            supabase_url="https://example.supabase.co",
            service_role_key="svc-key",
            http_client=http_client,
        )
        with pytest.raises(SupabaseNotFoundError):
            await client.select("cloud.workspaces")


@pytest.mark.asyncio
async def test_409_raises_supabase_conflict_error():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"message": "conflict"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = SupabaseClient(
            supabase_url="https://example.supabase.co",
            service_role_key="svc-key",
            http_client=http_client,
        )
        with pytest.raises(SupabaseConflictError):
            await client.insert("cloud.workspaces", {"name": "Acme"})


def test_connection_reuse_shared_httpx_client():
    # SupabaseClient defaults to a shared module-level AsyncClient for pooling.
    _reset_shared_async_client_for_tests()

    c1 = SupabaseClient(supabase_url="https://x.supabase.co", service_role_key="k")
    c2 = SupabaseClient(supabase_url="https://x.supabase.co", service_role_key="k")

    assert c1._client is c2._client

