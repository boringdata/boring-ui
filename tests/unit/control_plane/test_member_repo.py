"""Unit tests for SupabaseMemberRepository.

Bead: bd-1joj.5 (DB2)

Uses httpx.MockTransport to verify PostgREST queries without a real Supabase.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from control_plane.app.db.errors import SupabaseConflictError
from control_plane.app.db.supabase_client import SupabaseClient
from control_plane.app.db.member_repo import SupabaseMemberRepository


def _make_repo(handler) -> SupabaseMemberRepository:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    sc = SupabaseClient(
        supabase_url="https://test.supabase.co",
        service_role_key="svc-key",
        http_client=client,
    )
    return SupabaseMemberRepository(sc)


# ── Test: invite creates pending membership ─────────────────────────


@pytest.mark.asyncio
async def test_invite_creates_pending_membership():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["headers"] = dict(request.headers)
        return httpx.Response(
            201,
            json=[{
                "id": "mem_abc",
                "workspace_id": "ws_1",
                "email": "alice@example.com",
                "role": "admin",
                "status": "pending",
            }],
        )

    repo = _make_repo(handler)
    result = await repo.add_member("ws_1", {"email": "alice@example.com"})

    assert result["id"] == "mem_abc"
    assert result["status"] == "pending"
    assert result["role"] == "admin"
    assert seen["body"]["workspace_id"] == "ws_1"
    assert seen["body"]["status"] == "pending"
    assert seen["body"]["role"] == "admin"
    assert seen["headers"]["content-profile"] == "cloud"


# ── Test: duplicate pending invite returns 409 ──────────────────────


@pytest.mark.asyncio
async def test_duplicate_pending_invite_raises_conflict():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"message": "duplicate key"})

    repo = _make_repo(handler)
    with pytest.raises(SupabaseConflictError):
        await repo.add_member("ws_1", {"email": "alice@example.com"})


# ── Test: auto_accept_pending activates matching email ──────────────


@pytest.mark.asyncio
async def test_auto_accept_pending_activates_by_email():
    calls: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append({"method": request.method, "url": url})

        if request.method == "GET":
            # Return pending invites matching email
            return httpx.Response(200, json=[
                {"id": "mem_1", "workspace_id": "ws_1", "email": "Alice@example.com", "status": "pending"},
                {"id": "mem_2", "workspace_id": "ws_2", "email": "alice@example.com", "status": "pending"},
            ])
        else:
            # PATCH to activate
            body = json.loads(request.content)
            return httpx.Response(200, json=[{
                "id": calls[-1]["url"].split("id=eq.")[-1].split("&")[0],
                "status": "active",
                "user_id": body.get("user_id"),
            }])

    repo = _make_repo(handler)
    activated = await repo.auto_accept_pending("user-uuid-1", "alice@example.com")

    assert len(activated) == 2
    # Verify ilike used for case-insensitive match
    get_url = calls[0]["url"]
    assert "email=ilike.alice%40example.com" in get_url or "email=ilike.alice@example.com" in get_url


@pytest.mark.asyncio
async def test_auto_accept_pending_no_pending_returns_empty():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    repo = _make_repo(handler)
    result = await repo.auto_accept_pending("user-1", "nobody@example.com")
    assert result == []


# ── Test: remove_member sets status=removed (soft removal) ──────────


@pytest.mark.asyncio
async def test_remove_member_sets_status_removed():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=[{"id": "mem_1", "status": "removed"}])

    repo = _make_repo(handler)
    result = await repo.remove_member("ws_1", "mem_1")

    assert result is True
    assert seen["method"] == "PATCH"
    assert seen["body"]["status"] == "removed"
    assert "workspace_id=eq.ws_1" in seen["url"]
    assert "id=eq.mem_1" in seen["url"]


@pytest.mark.asyncio
async def test_remove_member_returns_false_for_missing():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    repo = _make_repo(handler)
    result = await repo.remove_member("ws_1", "mem_nonexistent")
    assert result is False


# ── Test: list_members excludes removed ─────────────────────────────


@pytest.mark.asyncio
async def test_list_members_excludes_removed():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[
            {"id": "mem_1", "status": "active"},
            {"id": "mem_2", "status": "pending"},
        ])

    repo = _make_repo(handler)
    results = await repo.list_members("ws_1")

    assert len(results) == 2
    assert "status=neq.removed" in seen["url"]
    assert "workspace_id=eq.ws_1" in seen["url"]


# ── Test: get_membership returns active member ──────────────────────


@pytest.mark.asyncio
async def test_get_membership_returns_active_member():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{
            "id": "mem_1",
            "workspace_id": "ws_1",
            "user_id": "user-1",
            "status": "active",
        }])

    repo = _make_repo(handler)
    result = await repo.get_membership("ws_1", "user-1")
    assert result is not None
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_get_membership_returns_none_for_non_member():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    repo = _make_repo(handler)
    result = await repo.get_membership("ws_1", "non-member")
    assert result is None


# ── Test: re-invite after removal works ─────────────────────────────


@pytest.mark.asyncio
async def test_reinvite_after_removal_works():
    """After removal, the unique partial index allows re-invite (status not in pending/active)."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=[{
            "id": "mem_new",
            "workspace_id": "ws_1",
            "email": "alice@example.com",
            "status": "pending",
        }])

    repo = _make_repo(handler)
    result = await repo.add_member("ws_1", {"email": "alice@example.com"})
    assert result["status"] == "pending"


# ── Test: protocol conformance ──────────────────────────────────────


def test_protocol_conformance():
    from control_plane.app.protocols import MemberRepository

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    client = httpx.AsyncClient(transport=transport)
    sc = SupabaseClient(
        supabase_url="https://test.supabase.co",
        service_role_key="svc-key",
        http_client=client,
    )
    repo = SupabaseMemberRepository(sc)
    assert isinstance(repo, MemberRepository)
