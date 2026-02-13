"""Unit tests for SupabaseAuditEmitter.

Bead: bd-1joj.8 (DB5)

Uses httpx.MockTransport to verify audit event writes without a real Supabase.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from control_plane.app.db.supabase_client import SupabaseClient
from control_plane.app.db.audit_emitter import (
    SupabaseAuditEmitter,
    _sanitize_payload,
)


def _make_emitter(handler) -> SupabaseAuditEmitter:
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    sc = SupabaseClient(
        supabase_url="https://test.supabase.co",
        service_role_key="svc-key",
        http_client=client,
    )
    return SupabaseAuditEmitter(sc)


# ── Test: emit writes to cloud.audit_events ─────────────────────────


@pytest.mark.asyncio
async def test_emit_writes_to_audit_events():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["headers"] = dict(request.headers)
        return httpx.Response(201, json=[{"id": 1}])

    emitter = _make_emitter(handler)
    await emitter.emit("workspace.create", {
        "workspace_id": "ws_1",
        "user_id": "user-1",
        "request_id": "req-123",
        "payload": {"name": "Acme"},
    })

    assert seen["method"] == "POST"
    assert "/audit_events" in seen["url"]
    assert seen["headers"]["content-profile"] == "cloud"


# ── Test: all required fields present ───────────────────────────────


@pytest.mark.asyncio
async def test_emit_includes_all_required_fields():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": 1}])

    emitter = _make_emitter(handler)
    await emitter.emit("member.invite", {
        "workspace_id": "ws_1",
        "user_id": "user-1",
        "request_id": "req-456",
        "payload": {"email": "alice@example.com"},
    })

    body = seen["body"]
    assert body["action"] == "member.invite"
    assert body["workspace_id"] == "ws_1"
    assert body["user_id"] == "user-1"
    assert body["request_id"] == "req-456"
    assert isinstance(body["payload"], dict)


# ── Test: user_id nullable for system actions ───────────────────────


@pytest.mark.asyncio
async def test_emit_user_id_nullable():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": 1}])

    emitter = _make_emitter(handler)
    await emitter.emit("system.cleanup", {
        "workspace_id": "ws_1",
        "request_id": "req-789",
    })

    assert seen["body"]["user_id"] is None


# ── Test: payload is valid JSON ─────────────────────────────────────


@pytest.mark.asyncio
async def test_emit_payload_is_dict():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": 1}])

    emitter = _make_emitter(handler)
    await emitter.emit("test.action", {
        "workspace_id": "ws_1",
        "payload": {"key": "value", "nested": {"a": 1}},
    })

    assert isinstance(seen["body"]["payload"], dict)
    assert seen["body"]["payload"]["key"] == "value"


@pytest.mark.asyncio
async def test_emit_non_dict_payload_defaults_to_empty():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": 1}])

    emitter = _make_emitter(handler)
    await emitter.emit("test.action", {
        "workspace_id": "ws_1",
        "payload": "not a dict",
    })

    assert seen["body"]["payload"] == {}


# ── Test: credentials never in payload ──────────────────────────────


def test_sanitize_payload_redacts_sensitive_keys():
    payload = {
        "name": "safe",
        "authorization": "Bearer secret-token",
        "apikey": "svc-key-xxx",
        "sprite_bearer_token": "sprite-secret",
        "nested": {
            "token": "inner-secret",
            "normal": "value",
        },
    }
    sanitized = _sanitize_payload(payload)
    assert sanitized["name"] == "safe"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["apikey"] == "[REDACTED]"
    assert sanitized["sprite_bearer_token"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["normal"] == "value"


@pytest.mark.asyncio
async def test_emit_sanitizes_payload():
    seen: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": 1}])

    emitter = _make_emitter(handler)
    await emitter.emit("test.action", {
        "workspace_id": "ws_1",
        "payload": {
            "workspace_name": "Acme",
            "password": "supersecret",
            "token": "my-token",
        },
    })

    payload = seen["body"]["payload"]
    assert payload["workspace_name"] == "Acme"
    assert payload["password"] == "[REDACTED]"
    assert payload["token"] == "[REDACTED]"


# ── Test: emit is non-blocking (does not raise on DB error) ─────────


@pytest.mark.asyncio
async def test_emit_does_not_raise_on_db_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "internal error"})

    emitter = _make_emitter(handler)
    # Should NOT raise — fire-and-forget
    await emitter.emit("test.action", {"workspace_id": "ws_1"})


@pytest.mark.asyncio
async def test_emit_does_not_raise_on_network_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    emitter = _make_emitter(handler)
    await emitter.emit("test.action", {"workspace_id": "ws_1"})


# ── Test: protocol conformance ──────────────────────────────────────


def test_protocol_conformance():
    from control_plane.app.protocols import AuditEmitter

    transport = httpx.MockTransport(lambda _: httpx.Response(201, json=[{"id": 1}]))
    client = httpx.AsyncClient(transport=transport)
    sc = SupabaseClient(
        supabase_url="https://test.supabase.co",
        service_role_key="svc-key",
        http_client=client,
    )
    emitter = SupabaseAuditEmitter(sc)
    assert isinstance(emitter, AuditEmitter)
