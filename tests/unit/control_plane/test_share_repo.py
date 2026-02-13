"""Unit tests for SupabaseShareLinkRepository.

Bead: bd-1joj.7 (DB4)

Uses httpx.MockTransport to verify PostgREST queries without a real Supabase.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
import pytest

from control_plane.app.db.supabase_client import SupabaseClient
from control_plane.app.db.share_repo import (
    SupabaseShareLinkRepository,
    _hash_token,
    _normalize_path,
)


def _make_repo(handler) -> SupabaseShareLinkRepository:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    sc = SupabaseClient(
        supabase_url="https://test.supabase.co",
        service_role_key="svc-key",
        http_client=client,
    )
    return SupabaseShareLinkRepository(sc)


# ── Test: create_link generates token and persists hash only ─────────


@pytest.mark.asyncio
async def test_create_generates_token_and_persists_hash():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{
            "id": "shr_1",
            "token_hash": seen.get("body", {}).get("token_hash", ""),
            "path": "/docs/readme.md",
        }])

    repo = _make_repo(handler)
    result = await repo.create_share({
        "workspace_id": "ws_1",
        "path": "/docs/readme.md",
        "access": "read",
        "created_by": "user-1",
    })

    # Plaintext token returned to caller
    assert "token" in result
    assert len(result["token"]) > 20

    # Hash stored in DB, not plaintext
    stored_hash = seen["body"]["token_hash"]
    assert stored_hash != result["token"]
    assert stored_hash == hashlib.sha256(result["token"].encode()).hexdigest()


# ── Test: plaintext token never stored in DB ─────────────────────────


@pytest.mark.asyncio
async def test_plaintext_token_not_in_db_payload():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": "shr_1"}])

    repo = _make_repo(handler)
    result = await repo.create_share({
        "workspace_id": "ws_1",
        "path": "/file.txt",
        "access": "read",
        "created_by": "user-1",
    })

    # DB payload should have token_hash but NOT plaintext token
    assert "token_hash" in seen["body"]
    assert "token" not in seen["body"]
    # And the plaintext should not appear as any value
    for v in seen["body"].values():
        assert v != result["token"]


# ── Test: get_link_by_token finds by hash ────────────────────────────


@pytest.mark.asyncio
async def test_get_share_finds_by_hash():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[{
            "id": "shr_1",
            "path": "/file.txt",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "revoked_at": None,
        }])

    repo = _make_repo(handler)
    token = "test-token-abc"
    result = await repo.get_share(token)

    assert result is not None
    assert result["id"] == "shr_1"
    # Should hash the token for lookup
    expected_hash = _hash_token(token)
    assert f"token_hash=eq.{expected_hash}" in seen["url"]


@pytest.mark.asyncio
async def test_get_share_returns_none_for_unknown():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    repo = _make_repo(handler)
    result = await repo.get_share("nonexistent-token")
    assert result is None


# ── Test: path normalization rejects traversal ───────────────────────


def test_normalize_path_rejects_traversal():
    with pytest.raises(ValueError, match="traversal"):
        _normalize_path("../../etc/passwd")

    with pytest.raises(ValueError, match="traversal"):
        _normalize_path("/docs/../../../etc/shadow")


def test_normalize_path_normalizes():
    assert _normalize_path("/docs/readme.md") == "/docs/readme.md"
    assert _normalize_path("docs/readme.md") == "/docs/readme.md"
    assert _normalize_path("/docs/./readme.md") == "/docs/readme.md"


@pytest.mark.asyncio
async def test_create_rejects_traversal_path():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=[{"id": "shr_1"}])

    repo = _make_repo(handler)
    with pytest.raises(ValueError, match="traversal"):
        await repo.create_share({
            "workspace_id": "ws_1",
            "path": "../../etc/passwd",
            "access": "read",
            "created_by": "user-1",
        })


# ── Test: access constrained to read/write ───────────────────────────


@pytest.mark.asyncio
async def test_create_rejects_invalid_access():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=[{"id": "shr_1"}])

    repo = _make_repo(handler)
    with pytest.raises(ValueError, match="access"):
        await repo.create_share({
            "workspace_id": "ws_1",
            "path": "/file.txt",
            "access": "admin",
            "created_by": "user-1",
        })


@pytest.mark.asyncio
async def test_create_accepts_valid_access():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(201, json=[{"id": "shr_1", "access": body.get("access")}])

    repo = _make_repo(handler)
    for access in ("read", "write"):
        result = await repo.create_share({
            "workspace_id": "ws_1",
            "path": "/file.txt",
            "access": access,
            "created_by": "user-1",
        })
        assert result is not None


# ── Test: default expiry is 24 hours ─────────────────────────────────


@pytest.mark.asyncio
async def test_create_default_expiry_24h():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": "shr_1"}])

    repo = _make_repo(handler)
    before = datetime.now(timezone.utc)
    await repo.create_share({
        "workspace_id": "ws_1",
        "path": "/file.txt",
        "access": "read",
        "created_by": "user-1",
    })
    after = datetime.now(timezone.utc)

    expires_at = datetime.fromisoformat(seen["body"]["expires_at"])
    expected_min = before + timedelta(hours=24)
    expected_max = after + timedelta(hours=24)
    assert expected_min <= expires_at <= expected_max


# ── Test: revoke sets revoked_at (soft revoke) ──────────────────────


@pytest.mark.asyncio
async def test_delete_share_sets_revoked_at():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=[{"id": "shr_1", "revoked_at": "2026-01-01T00:00:00Z"}])

    repo = _make_repo(handler)
    result = await repo.delete_share("shr_1")

    assert result is True
    assert seen["method"] == "PATCH"
    assert "revoked_at" in seen["body"]


@pytest.mark.asyncio
async def test_delete_share_returns_false_for_missing():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    repo = _make_repo(handler)
    result = await repo.delete_share("shr_nonexistent")
    assert result is False


# ── Test: list_shares returns all for workspace ──────────────────────


@pytest.mark.asyncio
async def test_list_shares_returns_all():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[
            {"id": "shr_1", "revoked_at": None},
            {"id": "shr_2", "revoked_at": "2026-01-01T00:00:00Z"},
        ])

    repo = _make_repo(handler)
    results = await repo.list_shares("ws_1")
    assert len(results) == 2


# ── Test: protocol conformance ──────────────────────────────────────


def test_protocol_conformance():
    from control_plane.app.protocols import ShareRepository

    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=[]))
    client = httpx.AsyncClient(transport=transport)
    sc = SupabaseClient(
        supabase_url="https://test.supabase.co",
        service_role_key="svc-key",
        http_client=client,
    )
    repo = SupabaseShareLinkRepository(sc)
    assert isinstance(repo, ShareRepository)
