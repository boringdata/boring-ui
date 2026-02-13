"""Unit tests for SupabaseWorkspaceRepository.

Bead: bd-1joj.4 (DB1)

Uses httpx.MockTransport to verify PostgREST queries without a real Supabase.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from control_plane.app.db.supabase_client import SupabaseClient
from control_plane.app.db.workspace_repo import SupabaseWorkspaceRepository


def _make_repo(handler) -> SupabaseWorkspaceRepository:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    sc = SupabaseClient(
        supabase_url="https://test.supabase.co",
        service_role_key="svc-key",
        http_client=client,
    )
    return SupabaseWorkspaceRepository(sc)


# ── Test: create inserts row and returns workspace_id ──────────────


@pytest.mark.asyncio
async def test_create_inserts_row_and_returns_workspace():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["headers"] = dict(request.headers)
        return httpx.Response(
            201,
            json=[{"id": "ws_abc123", "name": "Acme", "app_id": "boring-ui"}],
        )

    repo = _make_repo(handler)
    result = await repo.create({"name": "Acme", "owner_id": "u1"})

    assert result["id"] == "ws_abc123"
    assert seen["method"] == "POST"
    assert "/workspaces" in seen["url"]
    assert seen["headers"]["content-profile"] == "cloud"
    assert seen["body"]["name"] == "Acme"


# ── Test: app_id defaults to boring-ui ─────────────────────────────


@pytest.mark.asyncio
async def test_create_defaults_app_id():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": "ws_1", "app_id": "boring-ui"}])

    repo = _make_repo(handler)
    await repo.create({"name": "Test", "owner_id": "u1"})
    assert seen["body"]["app_id"] == "boring-ui"


@pytest.mark.asyncio
async def test_create_preserves_explicit_app_id():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": "ws_1", "app_id": "custom"}])

    repo = _make_repo(handler)
    await repo.create({"name": "Test", "app_id": "custom", "owner_id": "u1"})
    assert seen["body"]["app_id"] == "custom"


# ── Test: get_by_id returns workspace ──────────────────────────────


@pytest.mark.asyncio
async def test_get_returns_workspace():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": "ws_1", "name": "Acme"}])

    repo = _make_repo(handler)
    result = await repo.get("ws_1")
    assert result is not None
    assert result["id"] == "ws_1"


@pytest.mark.asyncio
async def test_get_returns_none_for_missing():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    repo = _make_repo(handler)
    result = await repo.get("ws_nonexistent")
    assert result is None


# ── Test: list_for_user returns only workspaces where user is active member ──


@pytest.mark.asyncio
async def test_list_for_user_returns_member_workspaces():
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        url = str(request.url)
        if "workspace_members" in url:
            # First call: membership lookup
            return httpx.Response(
                200, json=[{"workspace_id": "ws_1"}, {"workspace_id": "ws_2"}]
            )
        else:
            # Second call: workspace fetch
            return httpx.Response(
                200,
                json=[
                    {"id": "ws_1", "name": "One"},
                    {"id": "ws_2", "name": "Two"},
                ],
            )

    repo = _make_repo(handler)
    results = await repo.list_for_user("user-123")

    assert len(results) == 2
    assert results[0]["id"] == "ws_1"
    assert call_count == 2  # Two queries: members then workspaces


@pytest.mark.asyncio
async def test_list_for_user_empty_when_no_memberships():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    repo = _make_repo(handler)
    results = await repo.list_for_user("no-memberships")
    assert results == []


@pytest.mark.asyncio
async def test_list_for_user_filters_active_status():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "workspace_members" in url:
            seen["members_url"] = url
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[])

    repo = _make_repo(handler)
    await repo.list_for_user("user-123")

    assert "status=eq.active" in seen["members_url"]
    assert "user_id=eq.user-123" in seen["members_url"]


# ── Test: update returns updated workspace ─────────────────────────


@pytest.mark.asyncio
async def test_update_returns_updated_workspace():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json=[{"id": "ws_1", "name": "New Name"}]
        )

    repo = _make_repo(handler)
    result = await repo.update("ws_1", {"name": "New Name"})

    assert result is not None
    assert result["name"] == "New Name"
    assert seen["method"] == "PATCH"


@pytest.mark.asyncio
async def test_update_returns_none_for_missing():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    repo = _make_repo(handler)
    result = await repo.update("ws_nonexistent", {"name": "X"})
    assert result is None


# ── Test: workspace_id has ws_ prefix ──────────────────────────────


@pytest.mark.asyncio
async def test_create_returns_workspace_with_ws_prefix():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json=[{"id": "ws_abc123xyz", "name": "Test"}],
        )

    repo = _make_repo(handler)
    result = await repo.create({"name": "Test", "owner_id": "u1"})
    assert result["id"].startswith("ws_")


# ── Test: protocol conformance ─────────────────────────────────────


def test_protocol_conformance():
    from control_plane.app.protocols import WorkspaceRepository

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    client = httpx.AsyncClient(transport=transport)
    sc = SupabaseClient(
        supabase_url="https://test.supabase.co",
        service_role_key="svc-key",
        http_client=client,
    )
    repo = SupabaseWorkspaceRepository(sc)
    assert isinstance(repo, WorkspaceRepository)
