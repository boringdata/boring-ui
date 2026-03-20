from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from boring_ui.api.agents import HarnessHealth
from boring_ui.api.agents.pi_harness import PiHarness
from boring_ui.api.capabilities import create_capabilities_router
from boring_ui.api.config import APIConfig, AgentRuntimeConfig
from boring_ui.api.modules.control_plane.workspace_boundary_router_hosted import (
    _FlyReplayResult,
    create_workspace_boundary_router_hosted,
)
import boring_ui.api.modules.control_plane.workspace_boundary_router_hosted as boundary


def _hosted_backend_config(workspace_root: Path) -> APIConfig:
    return APIConfig(
        workspace_root=workspace_root,
        agents_mode="backend",
        control_plane_provider="neon",
        database_url="postgres://example.invalid/boring",
        auth_session_secret="test-secret",
        agents={"pi": AgentRuntimeConfig(enabled=True, port=8789)},
    )


def test_local_workspace_boundary_forwards_pi_requests_with_workspace_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(201, json={"session": {"id": "sess-1"}})

    config = _hosted_backend_config(tmp_path)
    harness = PiHarness(
        config,
        client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    harness.ensure_ready = lambda: asyncio.sleep(0)

    app = FastAPI()
    for router in harness.routes():
        app.include_router(router)
    app.include_router(create_workspace_boundary_router_hosted(config))

    async def fake_require_workspace_member(*args, **kwargs):
        class Session:
            user_id = "00000000-0000-0000-0000-000000000001"

        return Session()

    async def fake_try_fly_replay(*args, **kwargs):
        return _FlyReplayResult(None, is_local_workspace=True)

    monkeypatch.setattr(boundary, "_require_workspace_member", fake_require_workspace_member)
    monkeypatch.setattr(boundary, "_try_fly_replay", fake_try_fly_replay)

    client = TestClient(app)
    workspace_id = "11111111-1111-1111-1111-111111111111"
    response = client.post(
        f"/w/{workspace_id}/api/v1/agent/pi/sessions/create",
        json={},
        headers={"x-request-id": "req-boundary-pi"},
    )

    assert response.status_code == 201
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["x-workspace-id"] == workspace_id
    assert headers["x-boring-workspace-root"] == str(tmp_path.resolve())
    assert headers["authorization"].startswith("Bearer ")


def test_local_workspace_boundary_preserves_workspace_id_for_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _hosted_backend_config(tmp_path)
    harness = PiHarness(config)

    async def fake_healthy() -> HarnessHealth:
        return HarnessHealth(ok=True)

    harness.healthy = fake_healthy

    app = FastAPI()
    app.state.pi_harness = harness
    app.include_router(create_workspace_boundary_router_hosted(config))
    app.include_router(create_capabilities_router({"pi": False}, config=config), prefix="/api")

    async def fake_require_workspace_member(*args, **kwargs):
        class Session:
            user_id = "00000000-0000-0000-0000-000000000001"

        return Session()

    async def fake_try_fly_replay(*args, **kwargs):
        return _FlyReplayResult(None, is_local_workspace=True)

    monkeypatch.setattr(boundary, "_require_workspace_member", fake_require_workspace_member)
    monkeypatch.setattr(boundary, "_try_fly_replay", fake_try_fly_replay)

    client = TestClient(app)
    workspace_id = "11111111-1111-1111-1111-111111111111"
    response = client.get(f"/w/{workspace_id}/api/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["services"]["pi"]["url"] == f"/w/{workspace_id}"
