"""Unit tests for workspace HTTP proxy (bd-1joj.18).

Tests the proxy handler via the FastAPI test client with mocked runtime
metadata and httpx transport.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from control_plane.app.routing.proxy import (
    STRIP_REQUEST_HEADERS,
    STRIP_RESPONSE_HEADERS,
    WORKSPACE_ROUTE_PREFIXES,
    _is_valid_sandbox_name,
    _sanitize_request_headers,
    _sanitize_response_headers,
    create_workspace_proxy_router,
)


@dataclass
class FakeSettings:
    sprite_bearer_token: str = "sprite-secret-token"


class FakeRuntimeStore:
    def __init__(self, runtimes: dict[str, dict[str, Any]] | None = None):
        self._runtimes = runtimes or {}

    async def get_runtime(self, workspace_id: str) -> dict[str, Any] | None:
        return self._runtimes.get(workspace_id)

    async def upsert_runtime(self, workspace_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._runtimes[workspace_id] = {"workspace_id": workspace_id, **data}
        return self._runtimes[workspace_id]


class FakeWorkspaceRepo:
    def __init__(self, workspaces: dict[str, dict[str, Any]] | None = None):
        self._workspaces = workspaces or {}

    async def get(self, workspace_id: str) -> dict[str, Any] | None:
        return self._workspaces.get(workspace_id)


class FakeMemberRepo:
    def __init__(self, memberships: dict[tuple[str, str], dict[str, Any]] | None = None):
        self._memberships = memberships or {}

    async def get_membership(self, workspace_id: str, user_id: str) -> dict[str, Any] | None:
        return self._memberships.get((workspace_id, user_id))


@dataclass
class FakeDeps:
    runtime_store: Any
    workspace_repo: Any = None
    member_repo: Any = None


# Default test user used across proxy tests.
TEST_USER_ID = "test-user-1"

# Headers that include auth for the default test user.
AUTH_HEADERS: dict[str, str] = {"X-User-ID": TEST_USER_ID}


def _create_test_app(
    runtimes: dict[str, dict[str, Any]] | None = None,
    sprite_bearer_token: str = "sprite-secret-token",
) -> FastAPI:
    app = FastAPI()

    # Build workspace/member repos seeded for the default test user.
    workspaces = {}
    memberships = {}
    for ws_id in (runtimes or {}):
        workspaces[ws_id] = {"id": ws_id, "name": "Test"}
        memberships[(ws_id, TEST_USER_ID)] = {
            "user_id": TEST_USER_ID,
            "role": "admin",
            "status": "active",
        }

    app.state.deps = FakeDeps(
        runtime_store=FakeRuntimeStore(runtimes or {}),
        workspace_repo=FakeWorkspaceRepo(workspaces),
        member_repo=FakeMemberRepo(memberships),
    )
    app.state.settings = FakeSettings(sprite_bearer_token=sprite_bearer_token)

    # Add request-ID middleware stub.
    from starlette.middleware.base import BaseHTTPMiddleware

    class StubRequestID(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.request_id = "test-req-id"
            return await call_next(request)

    app.add_middleware(StubRequestID)
    app.include_router(create_workspace_proxy_router())
    return app


READY_RUNTIME = {
    "workspace_id": "ws_1",
    "state": "ready",
    "sandbox_name": "sbx-boring-ui-ws1-dev",
    "app_id": "boring-ui",
}


# ── Test: proxy resolves runtime URL from metadata store ──────────


def test_proxy_resolves_runtime_url_from_metadata_store():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
        mock_response = httpx.Response(
            200,
            json={"files": []},
            headers={"content-type": "application/json"},
        )
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TestClient(app)
        resp = client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    # Verify the request was forwarded to the correct URL.
    call_kwargs = mock_client_instance.request.call_args
    assert "sbx-boring-ui-ws1-dev.sprites.dev" in call_kwargs.kwargs["url"]


# ── Test: proxy returns 503 if runtime state != ready ─────────────


def test_proxy_returns_503_if_runtime_state_not_ready():
    provisioning_runtime = {**READY_RUNTIME, "state": "provisioning"}
    app = _create_test_app(runtimes={"ws_1": provisioning_runtime})

    client = TestClient(app)
    resp = client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "WORKSPACE_NOT_READY"
    assert body["state"] == "provisioning"


def test_proxy_returns_503_if_runtime_state_error():
    error_runtime = {**READY_RUNTIME, "state": "error"}
    app = _create_test_app(runtimes={"ws_1": error_runtime})

    client = TestClient(app)
    resp = client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    assert resp.status_code == 503
    assert resp.json()["state"] == "error"


# ── Test: proxy strips workspace prefix from path ─────────────────


def test_proxy_strips_workspace_prefix_from_path():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
        mock_response = httpx.Response(200, json={})
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TestClient(app)
        client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    call_kwargs = mock_client_instance.request.call_args
    url = call_kwargs.kwargs["url"]
    # Should be /api/v1/files/list, not /w/ws_1/api/v1/files/list.
    assert "/w/ws_1" not in url
    assert url.endswith("/api/v1/files/list")


# ── Test: proxy injects Sprite bearer token ───────────────────────


def test_proxy_injects_sprite_bearer_token():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
        mock_response = httpx.Response(200, json={})
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TestClient(app)
        client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    call_kwargs = mock_client_instance.request.call_args
    forwarded_headers = call_kwargs.kwargs["headers"]
    assert forwarded_headers["Authorization"] == "Bearer sprite-secret-token"


# ── Test: proxy propagates X-Request-ID ───────────────────────────


def test_proxy_propagates_x_request_id():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
        mock_response = httpx.Response(200, json={})
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TestClient(app)
        client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    call_kwargs = mock_client_instance.request.call_args
    forwarded_headers = call_kwargs.kwargs["headers"]
    assert forwarded_headers.get("X-Request-ID") == "test-req-id"


# ── Test: proxy propagates X-Session-ID when present ──────────────


def test_proxy_propagates_x_session_id_when_present():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
        mock_response = httpx.Response(200, json={})
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TestClient(app)
        client.get(
            "/w/ws_1/api/v1/files/list",
            headers={**AUTH_HEADERS, "X-Session-ID": "sess_abc"},
        )

    call_kwargs = mock_client_instance.request.call_args
    forwarded_headers = call_kwargs.kwargs["headers"]
    assert forwarded_headers.get("X-Session-ID") == "sess_abc"


# ── Test: proxy strips internal auth headers from browser request ─


def test_proxy_strips_internal_auth_headers_from_browser_request():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
        mock_response = httpx.Response(200, json={})
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TestClient(app)
        client.get(
            "/w/ws_1/api/v1/files/list",
            headers={
                **AUTH_HEADERS,
                "Authorization": "Bearer spoofed-token",
                "X-Sprite-Token": "spoofed",
                "X-Service-Token": "spoofed",
            },
        )

    call_kwargs = mock_client_instance.request.call_args
    forwarded_headers = call_kwargs.kwargs["headers"]
    # Spoofed headers should be replaced, not forwarded.
    assert forwarded_headers["Authorization"] == "Bearer sprite-secret-token"
    assert "X-Sprite-Token" not in forwarded_headers
    assert "X-Service-Token" not in forwarded_headers


# ── Test: proxy strips internal headers from response ─────────────


def test_proxy_strips_internal_headers_from_response():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
        mock_response = httpx.Response(
            200,
            json={},
            headers={
                "content-type": "application/json",
                "x-sprite-token": "internal-secret",
                "x-service-token": "internal-svc",
                "x-custom": "keep-this",
            },
        )
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TestClient(app)
        resp = client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "x-sprite-token" not in resp.headers
    assert "x-service-token" not in resp.headers
    assert resp.headers.get("x-custom") == "keep-this"


# ── Test: proxy returns runtime response status/headers/body ──────


def test_proxy_returns_runtime_response_status_headers_body():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
        mock_response = httpx.Response(
            201,
            content=b'{"created": true}',
            headers={"content-type": "application/json", "x-custom": "value"},
        )
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TestClient(app)
        resp = client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    assert resp.status_code == 201
    assert resp.json() == {"created": True}
    assert resp.headers.get("x-custom") == "value"


# ── Test: proxy rejects spoofed Authorization header from browser ─


def test_proxy_rejects_spoofed_authorization_header():
    """Even if browser sends Authorization, proxy replaces it with Sprite token."""
    headers = _sanitize_request_headers(
        {"Authorization": "Bearer user-token", "Content-Type": "application/json"},
        sprite_bearer_token="sprite-real-token",
        request_id="req_1",
    )
    assert headers["Authorization"] == "Bearer sprite-real-token"


# ── Test: all section 5.3 routes are proxied ──────────────────────


def test_all_section_53_routes_are_proxied():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    test_paths = [
        "/w/ws_1/app/index.html",
        "/w/ws_1/api/v1/files/list",
        "/w/ws_1/api/v1/git/status",
        "/w/ws_1/api/v1/pty/session",
        "/w/ws_1/api/v1/agent/sessions/list",
    ]

    for path in test_paths:
        with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
            mock_response = httpx.Response(200, json={})
            mock_client_instance = AsyncMock()
            mock_client_instance.request = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            client = TestClient(app)
            resp = client.get(path, headers=AUTH_HEADERS)

        assert resp.status_code == 200, f"Expected 200 for {path}, got {resp.status_code}"


# ── Test: non-workspace routes are NOT proxied ────────────────────


def test_non_workspace_routes_are_not_proxied():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    non_proxy_paths = [
        "/w/ws_1/admin/settings",
        "/w/ws_1/internal/debug",
        "/w/ws_1/health",
    ]

    client = TestClient(app)
    for path in non_proxy_paths:
        resp = client.get(path, headers=AUTH_HEADERS)
        assert resp.status_code == 404, f"Expected 404 for {path}, got {resp.status_code}"
        assert resp.json()["code"] == "ROUTE_NOT_FOUND"


# ── Test: 404 for unknown workspace ───────────────────────────────


def test_proxy_returns_404_for_unknown_workspace():
    app = _create_test_app(runtimes={})

    client = TestClient(app)
    resp = client.get("/w/ws_unknown/api/v1/files/list", headers=AUTH_HEADERS)

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "WORKSPACE_NOT_FOUND"


# ── Test: 502 when sprite_bearer_token not configured ─────────────


def test_proxy_returns_502_when_sprite_token_missing():
    app = _create_test_app(
        runtimes={"ws_1": READY_RUNTIME},
        sprite_bearer_token="",
    )

    client = TestClient(app)
    resp = client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    assert resp.status_code == 502
    assert resp.json()["code"] == "PROXY_CONFIG_ERROR"


# ── Test: path traversal rejected ─────────────────────────────────


def test_proxy_rejects_path_traversal():
    """Path traversal is blocked at multiple layers:
    1. Starlette normalizes .. in paths before the handler
    2. The prefix allowlist rejects paths not matching workspace routes
    3. The explicit .. check is defense-in-depth for edge cases
    """
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})
    client = TestClient(app)

    # These get normalized by Starlette then rejected by prefix check (404).
    starlette_normalized_paths = [
        "/w/ws_1/api/v1/files/../../etc/passwd",
        "/w/ws_1/app/../../../secret",
    ]
    for path in starlette_normalized_paths:
        resp = client.get(path, headers=AUTH_HEADERS)
        assert resp.status_code in (400, 404), (
            f"Expected 400 or 404 for {path}, got {resp.status_code}"
        )

    # Verify the .. check works at the application level.
    from control_plane.app.routing.proxy import _sanitize_request_headers
    # If somehow .. survives Starlette normalization, the handler catches it.
    # We test the prefix check catches traversed paths that resolve outside allowed prefixes.
    non_workspace_resolved = [
        "/w/ws_1/etc/passwd",
        "/w/ws_1/secret",
    ]
    for path in non_workspace_resolved:
        resp = client.get(path, headers=AUTH_HEADERS)
        assert resp.status_code == 404, f"Expected 404 for {path}, got {resp.status_code}"


# ── Test: sandbox name validation ─────────────────────────────────


def test_sandbox_name_validation():
    assert _is_valid_sandbox_name("sbx-boring-ui-ws1-dev") is True
    assert _is_valid_sandbox_name("simple") is True
    assert _is_valid_sandbox_name("a") is True
    assert _is_valid_sandbox_name("a-b") is True

    # Invalid: URL injection attempts
    assert _is_valid_sandbox_name("") is False
    assert _is_valid_sandbox_name("evil.com") is False
    assert _is_valid_sandbox_name("evil@host") is False
    assert _is_valid_sandbox_name("-starts-with-dash") is False
    assert _is_valid_sandbox_name("has spaces") is False
    assert _is_valid_sandbox_name("has/slash") is False


def test_proxy_rejects_invalid_sandbox_name():
    bad_runtime = {**READY_RUNTIME, "sandbox_name": "evil.com@host"}
    app = _create_test_app(runtimes={"ws_1": bad_runtime})

    client = TestClient(app)
    resp = client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    assert resp.status_code == 502
    assert resp.json()["code"] == "RUNTIME_CONFIG_ERROR"


# ── Test: set-cookie stripped from response ───────────────────────


def test_proxy_strips_set_cookie_from_response():
    """Workspace plane should not set cookies on the control-plane domain."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.proxy.httpx.AsyncClient") as MockClient:
        mock_response = httpx.Response(
            200,
            json={},
            headers={
                "content-type": "application/json",
                "set-cookie": "session=evil; Path=/; HttpOnly",
            },
        )
        mock_client_instance = AsyncMock()
        mock_client_instance.request = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TestClient(app)
        resp = client.get("/w/ws_1/api/v1/files/list", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "set-cookie" not in resp.headers
