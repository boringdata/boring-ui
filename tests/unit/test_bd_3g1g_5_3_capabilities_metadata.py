"""Guards for bd-3g1g.5.3 capabilities/registry metadata alignment."""

import os

from fastapi.testclient import TestClient

from boring_ui.api import create_app


def _routers_by_name(payload: dict) -> dict[str, dict]:
    routers = payload.get("routers", [])
    assert isinstance(routers, list)
    by_name: dict[str, dict] = {}
    for entry in routers:
        assert isinstance(entry, dict)
        name = entry.get("name")
        assert isinstance(name, str) and name
        assert name not in by_name, f"Duplicate router name in capabilities payload: {name}"
        by_name[name] = entry
    return by_name


def test_capabilities_router_metadata_includes_owner_and_canonical_families(monkeypatch) -> None:
    monkeypatch.setenv("CAPABILITIES_INCLUDE_CONTRACT_METADATA", "1")
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()

    by_name = _routers_by_name(payload)

    files = by_name["files"]
    assert files["owner_service"] == "workspace-core"
    assert files["canonical_families"] == ["/api/v1/files/*"]

    git = by_name["git"]
    assert git["owner_service"] == "workspace-core"
    assert git["canonical_families"] == ["/api/v1/git/*"]

    pty = by_name["pty"]
    assert pty["owner_service"] == "pty-service"
    assert "/ws/pty" in pty["canonical_families"]
    assert "/api/v1/pty/*" in pty["canonical_families"]

    chat = by_name["chat_claude_code"]
    assert chat["owner_service"] == "agent-normal"
    assert "/ws/agent/normal/*" in chat["canonical_families"]
    assert "/api/v1/agent/normal/*" in chat["canonical_families"]

    stream_alias = by_name["stream"]
    assert stream_alias["owner_service"] == "agent-normal"
    assert stream_alias["canonical_families"] == chat["canonical_families"]

    approval = by_name["approval"]
    assert approval["owner_service"] == "boring-ui"
    assert approval["canonical_families"] == ["/api/approval/*"]


def test_capabilities_contract_metadata_is_not_exposed_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CAPABILITIES_INCLUDE_CONTRACT_METADATA", raising=False)
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()

    by_name = _routers_by_name(payload)
    any_router = by_name["files"]
    assert "owner_service" not in any_router
    assert "canonical_families" not in any_router
