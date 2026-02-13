"""Unit tests for SSE proxy (bd-1joj.19).

Tests the SSE streaming proxy with mocked upstream responses
and verifies event forwarding, idle timeout, and error handling.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from control_plane.app.routing.sse_proxy import (
    DEFAULT_IDLE_TIMEOUT_SEC,
    _stream_sse_events,
    create_sse_proxy_router,
)


@dataclass
class FakeSettings:
    sprite_bearer_token: str = "sprite-secret-token"


class FakeRuntimeStore:
    def __init__(self, runtimes: dict[str, dict[str, Any]] | None = None):
        self._runtimes = runtimes or {}

    async def get_runtime(self, workspace_id: str) -> dict[str, Any] | None:
        return self._runtimes.get(workspace_id)


@dataclass
class FakeDeps:
    runtime_store: Any


READY_RUNTIME = {
    "workspace_id": "ws_1",
    "state": "ready",
    "sandbox_name": "sbx-boring-ui-ws1-dev",
    "app_id": "boring-ui",
}


def _create_test_app(
    runtimes: dict[str, dict[str, Any]] | None = None,
    sprite_bearer_token: str = "sprite-secret-token",
) -> FastAPI:
    app = FastAPI()
    app.state.deps = FakeDeps(runtime_store=FakeRuntimeStore(runtimes or {}))
    app.state.settings = FakeSettings(sprite_bearer_token=sprite_bearer_token)

    from starlette.middleware.base import BaseHTTPMiddleware

    class StubRequestID(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            request.state.request_id = "test-req-id"
            return await call_next(request)

    app.add_middleware(StubRequestID)
    app.include_router(create_sse_proxy_router())
    return app


# ── Test: SSE events forwarded from upstream ─────────────────────


def test_sse_events_forwarded_from_upstream():
    """Events from upstream are streamed to the browser client."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    sse_chunks = [
        b"event: message\ndata: {\"type\": \"text\"}\n\n",
        b"event: message\ndata: {\"type\": \"done\"}\n\n",
    ]

    with patch("control_plane.app.routing.sse_proxy.httpx.AsyncClient") as MockClient:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = lambda: _async_iter(sse_chunks)
        mock_response.aclose = AsyncMock()

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=httpx.Request("GET", "https://test.sprites.dev/api/v1/agent/sessions/s1/stream"))
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        client = TestClient(app)
        resp = client.get(
            "/w/ws_1/api/v1/agent/sessions/s1/stream",
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    # All chunks plus the close event should be in the response body.
    body = resp.content
    assert b"event: message" in body
    assert b"event: close" in body


# ── Test: upstream close sends final event ───────────────────────


def test_upstream_close_sends_final_close_event():
    """When upstream closes normally, a close event is sent to browser."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    # Upstream returns one chunk then closes.
    sse_chunks = [b"data: hello\n\n"]

    with patch("control_plane.app.routing.sse_proxy.httpx.AsyncClient") as MockClient:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = lambda: _async_iter(sse_chunks)
        mock_response.aclose = AsyncMock()

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=httpx.Request("GET", "https://test.sprites.dev/stream"))
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        client = TestClient(app)
        resp = client.get(
            "/w/ws_1/api/v1/agent/sessions/s1/stream",
            headers={"Accept": "text/event-stream"},
        )

    body = resp.content
    assert b"data: hello" in body
    assert b'event: close\ndata: {"reason": "upstream_closed"}' in body


# ── Test: non-SSE request returns 406 ────────────────────────────


def test_non_sse_request_returns_406():
    """Requests without Accept: text/event-stream get 406."""
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})
    client = TestClient(app)

    resp = client.get(
        "/w/ws_1/api/v1/agent/sessions/s1/stream",
        headers={"Accept": "application/json"},
    )

    assert resp.status_code == 406
    assert resp.json()["code"] == "NOT_SSE"


# ── Test: workspace not found returns 404 ────────────────────────


def test_workspace_not_found_returns_404():
    app = _create_test_app(runtimes={})
    client = TestClient(app)

    resp = client.get(
        "/w/ws_unknown/api/v1/agent/sessions/s1/stream",
        headers={"Accept": "text/event-stream"},
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "WORKSPACE_NOT_FOUND"


# ── Test: workspace not ready returns 503 ────────────────────────


def test_workspace_not_ready_returns_503():
    provisioning_runtime = {**READY_RUNTIME, "state": "provisioning"}
    app = _create_test_app(runtimes={"ws_1": provisioning_runtime})
    client = TestClient(app)

    resp = client.get(
        "/w/ws_1/api/v1/agent/sessions/s1/stream",
        headers={"Accept": "text/event-stream"},
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "WORKSPACE_NOT_READY"


# ── Test: invalid sandbox name returns 502 ───────────────────────


def test_invalid_sandbox_name_returns_502():
    bad_runtime = {**READY_RUNTIME, "sandbox_name": "evil.com@host"}
    app = _create_test_app(runtimes={"ws_1": bad_runtime})
    client = TestClient(app)

    resp = client.get(
        "/w/ws_1/api/v1/agent/sessions/s1/stream",
        headers={"Accept": "text/event-stream"},
    )

    assert resp.status_code == 502
    assert resp.json()["code"] == "RUNTIME_CONFIG_ERROR"


# ── Test: missing sprite token returns 502 ───────────────────────


def test_missing_sprite_token_returns_502():
    app = _create_test_app(
        runtimes={"ws_1": READY_RUNTIME},
        sprite_bearer_token="",
    )
    client = TestClient(app)

    resp = client.get(
        "/w/ws_1/api/v1/agent/sessions/s1/stream",
        headers={"Accept": "text/event-stream"},
    )

    assert resp.status_code == 502
    assert resp.json()["code"] == "PROXY_CONFIG_ERROR"


# ── Test: Sprite bearer injected in upstream request ─────────────


def test_sprite_bearer_injected_in_upstream_request():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.sse_proxy.httpx.AsyncClient") as MockClient:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = lambda: _async_iter([b"data: x\n\n"])
        mock_response.aclose = AsyncMock()

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=httpx.Request("GET", "https://test.sprites.dev/stream"))
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        client = TestClient(app)
        client.get(
            "/w/ws_1/api/v1/agent/sessions/s1/stream",
            headers={"Accept": "text/event-stream"},
        )

    # Check the headers passed to build_request.
    build_call = mock_client.build_request.call_args
    headers = build_call.kwargs.get("headers") or build_call.args[2] if len(build_call.args) > 2 else build_call.kwargs["headers"]
    assert headers["Authorization"] == "Bearer sprite-secret-token"


# ── Test: X-Request-ID propagated to upstream ────────────────────


def test_x_request_id_propagated_to_upstream():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.sse_proxy.httpx.AsyncClient") as MockClient:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = lambda: _async_iter([b"data: x\n\n"])
        mock_response.aclose = AsyncMock()

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=httpx.Request("GET", "https://test.sprites.dev/stream"))
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        client = TestClient(app)
        client.get(
            "/w/ws_1/api/v1/agent/sessions/s1/stream",
            headers={"Accept": "text/event-stream"},
        )

    build_call = mock_client.build_request.call_args
    headers = build_call.kwargs.get("headers") or build_call.args[2] if len(build_call.args) > 2 else build_call.kwargs["headers"]
    assert headers.get("X-Request-ID") == "test-req-id"


# ── Test: X-Request-ID in response headers ───────────────────────


def test_x_request_id_in_response_headers():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.sse_proxy.httpx.AsyncClient") as MockClient:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = lambda: _async_iter([b"data: x\n\n"])
        mock_response.aclose = AsyncMock()

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=httpx.Request("GET", "https://test.sprites.dev/stream"))
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        client = TestClient(app)
        resp = client.get(
            "/w/ws_1/api/v1/agent/sessions/s1/stream",
            headers={"Accept": "text/event-stream"},
        )

    assert resp.headers.get("x-request-id") == "test-req-id"


# ── Test: upstream connect error returns 502 ─────────────────────


def test_upstream_connect_error_returns_502():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.sse_proxy.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=httpx.Request("GET", "https://test.sprites.dev/stream"))
        mock_client.send = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        client = TestClient(app)
        resp = client.get(
            "/w/ws_1/api/v1/agent/sessions/s1/stream",
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 502
    assert resp.json()["code"] == "RUNTIME_UNAVAILABLE"


# ── Test: upstream timeout returns 504 ───────────────────────────


def test_upstream_timeout_returns_504():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.sse_proxy.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=httpx.Request("GET", "https://test.sprites.dev/stream"))
        mock_client.send = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        client = TestClient(app)
        resp = client.get(
            "/w/ws_1/api/v1/agent/sessions/s1/stream",
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 504
    assert resp.json()["code"] == "PROXY_TIMEOUT"


# ── Test: upstream non-200 status forwarded ──────────────────────


def test_upstream_non_200_returns_upstream_error():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.sse_proxy.httpx.AsyncClient") as MockClient:
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.aread = AsyncMock(return_value=b"Internal Server Error")
        mock_response.aclose = AsyncMock()

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=httpx.Request("GET", "https://test.sprites.dev/stream"))
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        client = TestClient(app)
        resp = client.get(
            "/w/ws_1/api/v1/agent/sessions/s1/stream",
            headers={"Accept": "text/event-stream"},
        )

    assert resp.status_code == 500
    assert resp.json()["code"] == "UPSTREAM_ERROR"


# ── Test: Cache-Control and Connection headers set ───────────────


def test_response_has_cache_control_and_connection_headers():
    app = _create_test_app(runtimes={"ws_1": READY_RUNTIME})

    with patch("control_plane.app.routing.sse_proxy.httpx.AsyncClient") as MockClient:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aiter_bytes = lambda: _async_iter([b"data: x\n\n"])
        mock_response.aclose = AsyncMock()

        mock_client = AsyncMock()
        mock_client.build_request = MagicMock(return_value=httpx.Request("GET", "https://test.sprites.dev/stream"))
        mock_client.send = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()
        MockClient.return_value = mock_client

        client = TestClient(app)
        resp = client.get(
            "/w/ws_1/api/v1/agent/sessions/s1/stream",
            headers={"Accept": "text/event-stream"},
        )

    assert resp.headers.get("cache-control") == "no-cache"


# ── Test: _stream_sse_events idle timeout ────────────────────────


@pytest.mark.asyncio
async def test_stream_sse_events_idle_timeout():
    """With a very short idle timeout, the generator should emit a timeout event."""
    mock_response = AsyncMock()

    async def slow_iter():
        yield b"data: first\n\n"
        # Simulate idle by sleeping longer than the timeout.
        await asyncio.sleep(0.3)
        yield b"data: second\n\n"

    mock_response.aiter_bytes = slow_iter
    mock_response.aclose = AsyncMock()

    chunks = []
    async for chunk in _stream_sse_events(mock_response, request_id="test", idle_timeout_sec=0.05):
        chunks.append(chunk)

    # First chunk should be forwarded, then timeout before second chunk.
    assert chunks[0] == b"data: first\n\n"
    assert b"idle_timeout" in chunks[-1]
    assert mock_response.aclose.called


# ── Helpers ──────────────────────────────────────────────────────


async def _async_iter(items):
    """Convert a list to an async iterator."""
    for item in items:
        yield item
