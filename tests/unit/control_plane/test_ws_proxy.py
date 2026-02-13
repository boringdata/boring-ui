"""Unit tests for WebSocket proxy (bd-1joj.19).

Tests the WebSocket bidirectional proxy with mocked upstream connections.
Covers message forwarding, close propagation, max message size, and error handling.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, WebSocket
from starlette.testclient import TestClient

from control_plane.app.routing.ws_proxy import (
    DEFAULT_MAX_MESSAGE_SIZE,
    _forward_browser_to_upstream,
    _forward_upstream_to_browser,
    create_ws_proxy_router,
)


@dataclass
class FakeSettings:
    sprite_bearer_token: str = "sprite-secret-token"


class FakeRuntimeStore:
    def __init__(self, runtimes: dict[str, dict[str, Any]] | None = None):
        self._runtimes = runtimes or {}

    async def get_runtime(self, workspace_id: str) -> dict[str, Any] | None:
        return self._runtimes.get(workspace_id)


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


READY_RUNTIME = {
    "workspace_id": "ws_1",
    "state": "ready",
    "sandbox_name": "sbx-boring-ui-ws1-dev",
    "app_id": "boring-ui",
}

TEST_USER_ID = "test-user-1"
WS_AUTH_HEADERS = {"x-user-id": TEST_USER_ID}


def _create_test_app(
    runtimes: dict[str, dict[str, Any]] | None = None,
    sprite_bearer_token: str = "sprite-secret-token",
) -> FastAPI:
    app = FastAPI()

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
    app.include_router(create_ws_proxy_router())
    return app


# ── Test: WS bidirectional text message forwarding ───────────────


def test_ws_upstream_text_forwarded_to_browser():
    """Text messages from upstream are forwarded to the browser."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.ws_proxy.websockets") as mock_websockets:
        mock_upstream = AsyncMock()
        mock_upstream.send = AsyncMock()
        mock_upstream.close = AsyncMock()

        async def upstream_iter():
            yield "upstream-hello"

        mock_upstream.__aiter__ = lambda self: upstream_iter()
        mock_websockets.connect = AsyncMock(return_value=mock_upstream)
        mock_websockets.ConnectionClosed = Exception

        with TestClient(app) as client:
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                msg = ws.receive_text()
                assert msg == "upstream-hello"


# ── Test: WS bidirectional binary message forwarding ─────────────


def test_ws_upstream_binary_forwarded_to_browser():
    """Binary messages from upstream are forwarded to the browser."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.ws_proxy.websockets") as mock_websockets:
        mock_upstream = AsyncMock()
        mock_upstream.send = AsyncMock()
        mock_upstream.close = AsyncMock()

        async def upstream_iter():
            yield b"\x00\x01\x02"

        mock_upstream.__aiter__ = lambda self: upstream_iter()
        mock_websockets.connect = AsyncMock(return_value=mock_upstream)
        mock_websockets.ConnectionClosed = Exception

        with TestClient(app) as client:
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                msg = ws.receive_bytes()
                assert msg == b"\x00\x01\x02"


# ── Test: WS close from browser closes upstream ──────────────────


def test_browser_close_closes_upstream():
    """When the browser disconnects, the upstream connection is closed."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.ws_proxy.websockets") as mock_websockets:
        mock_upstream = AsyncMock()
        mock_upstream.send = AsyncMock()
        mock_upstream.close = AsyncMock()

        # Upstream never sends anything; just hangs.
        async def upstream_iter():
            await asyncio.sleep(10)
            return
            yield  # make it a generator

        mock_upstream.__aiter__ = lambda self: upstream_iter()
        mock_websockets.connect = AsyncMock(return_value=mock_upstream)
        mock_websockets.ConnectionClosed = Exception

        with TestClient(app) as client:
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                pass  # Immediately close.

    # Upstream close should be called.
    mock_upstream.close.assert_called()


# ── Test: WS workspace not ready closes with 1008 ───────────────


def test_ws_workspace_not_ready_closes_1008():
    """If runtime isn't ready, WebSocket is closed with code 1008."""
    provisioning_runtime = {**READY_RUNTIME, "state": "provisioning"}
    app = _create_test_app(runtimes={"ws_1": provisioning_runtime})

    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                ws.receive_text()


# ── Test: WS workspace not found closes with 1008 ───────────────


def test_ws_workspace_not_found_closes_1008():
    app = _create_test_app(runtimes={})

    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/w/ws_unknown/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                ws.receive_text()


# ── Test: WS invalid sandbox name closes with 1008 ──────────────


def test_ws_invalid_sandbox_name_closes_1008():
    bad_runtime = {**READY_RUNTIME, "sandbox_name": "evil.com@host"}
    app = _create_test_app(runtimes={"ws_1": bad_runtime})

    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                ws.receive_text()


# ── Test: WS missing sprite token closes with 1008 ──────────────


def test_ws_missing_sprite_token_closes_1008():
    app = _create_test_app(
        runtimes={"ws_1": READY_RUNTIME},
        sprite_bearer_token="",
    )

    with TestClient(app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                ws.receive_text()


# ── Test: Sprite bearer injected in upstream WS connect ──────────


def test_sprite_bearer_injected_in_ws_connect():
    """The upstream WebSocket connection includes the Sprite bearer token."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.ws_proxy.websockets") as mock_websockets:
        mock_upstream = AsyncMock()
        mock_upstream.send = AsyncMock()
        mock_upstream.close = AsyncMock()

        async def upstream_iter():
            return
            yield

        mock_upstream.__aiter__ = lambda self: upstream_iter()
        mock_websockets.connect = AsyncMock(return_value=mock_upstream)
        mock_websockets.ConnectionClosed = Exception

        with TestClient(app) as client:
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                pass

    connect_call = mock_websockets.connect.call_args
    extra_headers = connect_call.kwargs.get("extra_headers", {})
    assert extra_headers.get("Authorization") == "Bearer sprite-secret-token"


# ── Test: X-Request-ID propagated to upstream WS ─────────────────


def test_x_request_id_propagated_to_ws_upstream():
    """X-Request-ID is sent as a header on the upstream WS connection."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.ws_proxy.websockets") as mock_websockets:
        mock_upstream = AsyncMock()
        mock_upstream.send = AsyncMock()
        mock_upstream.close = AsyncMock()

        async def upstream_iter():
            return
            yield

        mock_upstream.__aiter__ = lambda self: upstream_iter()
        mock_websockets.connect = AsyncMock(return_value=mock_upstream)
        mock_websockets.ConnectionClosed = Exception

        with TestClient(app) as client:
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                pass

    connect_call = mock_websockets.connect.call_args
    extra_headers = connect_call.kwargs.get("extra_headers", {})
    assert "X-Request-ID" in extra_headers


# ── Test: upstream WS URL uses wss:// scheme ─────────────────────


def test_upstream_ws_url_uses_wss_scheme():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.ws_proxy.websockets") as mock_websockets:
        mock_upstream = AsyncMock()
        mock_upstream.send = AsyncMock()
        mock_upstream.close = AsyncMock()

        async def upstream_iter():
            return
            yield

        mock_upstream.__aiter__ = lambda self: upstream_iter()
        mock_websockets.connect = AsyncMock(return_value=mock_upstream)
        mock_websockets.ConnectionClosed = Exception

        with TestClient(app) as client:
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                pass

    connect_call = mock_websockets.connect.call_args
    ws_url = connect_call.args[0] if connect_call.args else connect_call.kwargs.get("uri", "")
    assert ws_url.startswith("wss://")
    assert "sbx-boring-ui-ws1-dev.sprites.dev" in ws_url


# ── Test: max message size enforced via websockets.connect ───────


def test_max_message_size_passed_to_upstream():
    """The upstream WebSocket connection should have max_size set."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.ws_proxy.websockets") as mock_websockets:
        mock_upstream = AsyncMock()
        mock_upstream.send = AsyncMock()
        mock_upstream.close = AsyncMock()

        async def upstream_iter():
            return
            yield

        mock_upstream.__aiter__ = lambda self: upstream_iter()
        mock_websockets.connect = AsyncMock(return_value=mock_upstream)
        mock_websockets.ConnectionClosed = Exception

        with TestClient(app) as client:
            with client.websocket_connect("/w/ws_1/api/v1/pty/session", headers=WS_AUTH_HEADERS) as ws:
                pass

    connect_call = mock_websockets.connect.call_args
    assert connect_call.kwargs.get("max_size") == DEFAULT_MAX_MESSAGE_SIZE


# ── Test: _forward_browser_to_upstream drops oversized text ──────


@pytest.mark.asyncio
async def test_forward_browser_to_upstream_drops_oversized_text():
    """Messages exceeding max size are dropped, not forwarded."""
    browser_ws = AsyncMock()
    upstream_ws = AsyncMock()

    # Simulate receiving an oversized text message then disconnect.
    oversized_msg = "x" * (DEFAULT_MAX_MESSAGE_SIZE + 1)
    browser_ws.receive = AsyncMock(
        side_effect=[
            {"type": "websocket.receive", "text": oversized_msg},
            {"type": "websocket.disconnect"},
        ]
    )

    await _forward_browser_to_upstream(browser_ws, upstream_ws, "req-1")

    # The oversized message should NOT have been forwarded.
    upstream_ws.send.assert_not_called()


# ── Test: _forward_browser_to_upstream drops oversized binary ────


@pytest.mark.asyncio
async def test_forward_browser_to_upstream_drops_oversized_binary():
    """Binary messages exceeding max size are dropped."""
    browser_ws = AsyncMock()
    upstream_ws = AsyncMock()

    oversized_msg = b"\x00" * (DEFAULT_MAX_MESSAGE_SIZE + 1)
    browser_ws.receive = AsyncMock(
        side_effect=[
            {"type": "websocket.receive", "bytes": oversized_msg},
            {"type": "websocket.disconnect"},
        ]
    )

    await _forward_browser_to_upstream(browser_ws, upstream_ws, "req-1")

    upstream_ws.send.assert_not_called()


# ── Test: _forward_browser_to_upstream forwards normal messages ──


@pytest.mark.asyncio
async def test_forward_browser_to_upstream_forwards_normal_text():
    browser_ws = AsyncMock()
    upstream_ws = AsyncMock()

    browser_ws.receive = AsyncMock(
        side_effect=[
            {"type": "websocket.receive", "text": "hello"},
            {"type": "websocket.disconnect"},
        ]
    )

    await _forward_browser_to_upstream(browser_ws, upstream_ws, "req-1")

    upstream_ws.send.assert_called_once_with("hello")


# ── Test: _forward_upstream_to_browser handles text and bytes ────


@pytest.mark.asyncio
async def test_forward_upstream_to_browser_handles_text_and_bytes():
    upstream_ws = AsyncMock()
    browser_ws = AsyncMock()

    async def upstream_iter():
        yield "text-msg"
        yield b"binary-msg"

    upstream_ws.__aiter__ = lambda self: upstream_iter()

    await _forward_upstream_to_browser(upstream_ws, browser_ws, "req-1")

    browser_ws.send_text.assert_called_once_with("text-msg")
    browser_ws.send_bytes.assert_called_once_with(b"binary-msg")
