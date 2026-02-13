from __future__ import annotations

from typing import Any

import httpx
import pytest

from control_plane.app.db.runtime_store import SupabaseRuntimeMetadataStore
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
async def test_upsert_runtime_creates_new_row():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen["method"] = request.method
        seen["headers"] = dict(request.headers)
        body = _json.loads(request.content.decode())
        seen["body"] = body
        return httpx.Response(
            201,
            json=[{
                "workspace_id": "ws_1",
                "app_id": body.get("app_id", "boring-ui"),
                "state": body.get("state", "provisioning"),
                "release_id": body.get("release_id"),
                "sandbox_name": body.get("sandbox_name"),
                "bundle_sha256": body.get("bundle_sha256"),
                "updated_at": body.get("updated_at"),
            }],
        )

    http, client = _make_client(handler)
    async with http:
        store = SupabaseRuntimeMetadataStore(client)
        rt = await store.upsert_runtime("ws_1", {
            "state": "provisioning",
            "release_id": "rel_1",
            "sandbox_name": "sbx-boring-ui-ws_1-dev",
            "bundle_sha256": "abc123",
        })

    assert rt["workspace_id"] == "ws_1"
    assert rt["app_id"] == "boring-ui"
    assert rt["state"] == "provisioning"
    assert rt["release_id"] == "rel_1"
    assert rt["sandbox_name"] == "sbx-boring-ui-ws_1-dev"
    # Upsert should use POST with merge-duplicates.
    assert seen["method"] == "POST"
    assert "merge-duplicates" in seen["headers"].get("prefer", "")


@pytest.mark.asyncio
async def test_upsert_runtime_updates_existing_row():
    """Upsert on existing workspace_id merges data (ON CONFLICT DO UPDATE)."""
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode())
        seen["body"] = body
        return httpx.Response(
            200,
            json=[{
                "workspace_id": "ws_1",
                "app_id": "boring-ui",
                "state": "ready",
                "release_id": "rel_2",
                "sandbox_name": "sbx-boring-ui-ws_1-dev",
                "updated_at": body.get("updated_at"),
            }],
        )

    http, client = _make_client(handler)
    async with http:
        store = SupabaseRuntimeMetadataStore(client)
        rt = await store.upsert_runtime("ws_1", {
            "state": "ready",
            "release_id": "rel_2",
        })

    assert rt["state"] == "ready"
    assert rt["release_id"] == "rel_2"


@pytest.mark.asyncio
async def test_get_runtime_returns_row():
    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert "workspace_id=eq.ws_1" in url
        return httpx.Response(
            200,
            json=[{
                "workspace_id": "ws_1",
                "app_id": "boring-ui",
                "state": "ready",
            }],
        )

    http, client = _make_client(handler)
    async with http:
        store = SupabaseRuntimeMetadataStore(client)
        rt = await store.get_runtime("ws_1")

    assert rt is not None
    assert rt["workspace_id"] == "ws_1"


@pytest.mark.asyncio
async def test_get_runtime_returns_none_when_missing():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    http, client = _make_client(handler)
    async with http:
        store = SupabaseRuntimeMetadataStore(client)
        rt = await store.get_runtime("ws_nonexistent")

    assert rt is None


@pytest.mark.asyncio
async def test_runtime_exactly_one_row_per_workspace_via_upsert():
    """Upsert always targets workspace_id PK so only one row per workspace."""
    seen_bodies: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode())
        seen_bodies.append(body)
        return httpx.Response(200, json=[{"workspace_id": "ws_1", **body}])

    http, client = _make_client(handler)
    async with http:
        store = SupabaseRuntimeMetadataStore(client)
        await store.upsert_runtime("ws_1", {"state": "provisioning"})
        await store.upsert_runtime("ws_1", {"state": "ready"})

    # Both calls should target same workspace_id.
    assert all(b["workspace_id"] == "ws_1" for b in seen_bodies)


@pytest.mark.asyncio
async def test_update_state_sets_error_fields():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode())
        seen["body"] = body
        return httpx.Response(
            200,
            json=[{"workspace_id": "ws_1", "state": "error", **body}],
        )

    http, client = _make_client(handler)
    async with http:
        store = SupabaseRuntimeMetadataStore(client)
        rt = await store.update_state(
            "ws_1",
            "error",
            error_code="BOOTSTRAP_FAIL",
            error_detail="Process exited with code 1",
        )

    assert rt is not None
    assert rt["state"] == "error"
    assert seen["body"]["last_error_code"] == "BOOTSTRAP_FAIL"
    assert seen["body"]["last_error_detail"] == "Process exited with code 1"
    assert "updated_at" in seen["body"]


@pytest.mark.asyncio
async def test_update_state_clears_error_fields_on_non_error_state():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode())
        seen["body"] = body
        return httpx.Response(
            200,
            json=[{"workspace_id": "ws_1", **body}],
        )

    http, client = _make_client(handler)
    async with http:
        store = SupabaseRuntimeMetadataStore(client)
        await store.update_state("ws_1", "ready")

    # Error fields should be explicitly set to None (cleared).
    assert seen["body"]["last_error_code"] is None
    assert seen["body"]["last_error_detail"] is None


@pytest.mark.asyncio
async def test_upsert_runtime_defaults_app_id():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        body = _json.loads(request.content.decode())
        seen["body"] = body
        return httpx.Response(200, json=[body])

    http, client = _make_client(handler)
    async with http:
        store = SupabaseRuntimeMetadataStore(client)
        await store.upsert_runtime("ws_1", {"state": "provisioning"})

    assert seen["body"]["app_id"] == "boring-ui"


@pytest.mark.asyncio
async def test_update_state_returns_none_when_no_row():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    http, client = _make_client(handler)
    async with http:
        store = SupabaseRuntimeMetadataStore(client)
        result = await store.update_state("ws_nonexistent", "ready")

    assert result is None
