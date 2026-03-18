"""Tests for FlyReplayRouter (fly-replay routing)."""

import pytest
from unittest.mock import AsyncMock
from starlette.testclient import TestClient
from fastapi import FastAPI, Request

from boring_ui.api.workspace.router_protocol import WorkspaceRouter
from boring_ui.api.workspace.fly_router import FlyReplayRouter


def test_satisfies_protocol():
    router = FlyReplayRouter(lookup_machine_id=AsyncMock(return_value="m-1"))
    assert isinstance(router, WorkspaceRouter)


@pytest.mark.asyncio
async def test_route_returns_fly_replay_header():
    lookup = AsyncMock(return_value="mach_abc123")
    router = FlyReplayRouter(lookup_machine_id=lookup)
    request = AsyncMock(spec=Request)

    resp = await router.route("ws-42", request)

    assert resp.status_code == 200
    assert resp.headers["fly-replay"] == "instance=mach_abc123"
    lookup.assert_called_once_with("ws-42")


@pytest.mark.asyncio
async def test_route_returns_404_when_not_found():
    lookup = AsyncMock(return_value=None)
    router = FlyReplayRouter(lookup_machine_id=lookup)
    request = AsyncMock(spec=Request)

    resp = await router.route("ws-missing", request)

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_route_works_with_different_workspaces():
    async def lookup(ws_id):
        return {"ws-1": "mach_aaa", "ws-2": "mach_bbb"}.get(ws_id)

    router = FlyReplayRouter(lookup_machine_id=lookup)
    request = AsyncMock(spec=Request)

    r1 = await router.route("ws-1", request)
    r2 = await router.route("ws-2", request)
    r3 = await router.route("ws-3", request)

    assert r1.headers["fly-replay"] == "instance=mach_aaa"
    assert r2.headers["fly-replay"] == "instance=mach_bbb"
    assert r3.status_code == 404
