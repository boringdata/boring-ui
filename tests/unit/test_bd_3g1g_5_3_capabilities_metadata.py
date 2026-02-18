"""Guards for bd-3g1g.5.3 capabilities/registry metadata alignment."""

from fastapi.testclient import TestClient

from boring_ui.api import create_app, RouterRegistry
from boring_ui.api.capabilities import RouterInfo


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


def test_registry_register_normalizes_string_lists() -> None:
    registry = RouterRegistry()

    # Intentionally pass strings to ensure we don't create ["f","i","l","e","s"].
    # This is a defensive normalization behavior; callers should still pass lists.
    registry.register(
        name="demo",
        prefix="/api/demo",
        factory=lambda: None,  # type: ignore[arg-type]
        tags="files",  # type: ignore[arg-type]
        required_capabilities="cap.demo",  # type: ignore[arg-type]
        canonical_families="/api/demo/*",  # type: ignore[arg-type]
    )

    entry = registry.get("demo")
    assert entry is not None
    info, _ = entry
    assert isinstance(info, RouterInfo)
    assert info.tags == ["files"]
    assert info.required_capabilities == ["cap.demo"]
    assert info.canonical_families == ["/api/demo/*"]


def test_capabilities_router_metadata_includes_owner_and_canonical_families(monkeypatch) -> None:
    monkeypatch.setenv("CAPABILITIES_INCLUDE_CONTRACT_METADATA", "1")
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()

    by_name = _routers_by_name(payload)
    for entry in by_name.values():
        assert "contract_metadata" in entry
        assert entry["contract_metadata_included"] is True
        assert isinstance(entry["contract_metadata"], dict)
        assert isinstance(entry["contract_metadata"]["canonical_families"], list)
        assert all(isinstance(value, str) for value in entry["contract_metadata"]["canonical_families"])

    files = by_name["files"]
    assert files["contract_metadata"]["owner_service"] == "workspace-core"
    assert files["contract_metadata"]["canonical_families"] == ["/api/v1/files/*"]

    git = by_name["git"]
    assert git["contract_metadata"]["owner_service"] == "workspace-core"
    assert git["contract_metadata"]["canonical_families"] == ["/api/v1/git/*"]

    pty = by_name["pty"]
    assert pty["contract_metadata"]["owner_service"] == "pty-service"
    assert "/ws/pty" in pty["contract_metadata"]["canonical_families"]
    assert "/api/v1/pty/*" in pty["contract_metadata"]["canonical_families"]

    chat = by_name["chat_claude_code"]
    assert chat["contract_metadata"]["owner_service"] == "agent-normal"
    assert "/ws/agent/normal/*" in chat["contract_metadata"]["canonical_families"]
    assert "/api/v1/agent/normal/*" in chat["contract_metadata"]["canonical_families"]

    stream_alias = by_name["stream"]
    assert stream_alias["contract_metadata"]["owner_service"] == "agent-normal"
    assert stream_alias["contract_metadata"]["canonical_families"] == chat["contract_metadata"]["canonical_families"]

    approval = by_name["approval"]
    assert approval["contract_metadata"]["owner_service"] == "boring-ui"
    assert approval["contract_metadata"]["canonical_families"] == ["/api/approval/*"]


def test_capabilities_contract_metadata_is_not_exposed_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CAPABILITIES_INCLUDE_CONTRACT_METADATA", raising=False)
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()

    by_name = _routers_by_name(payload)
    for entry in by_name.values():
        assert "contract_metadata" in entry
        assert entry["contract_metadata_included"] is False
        assert entry["contract_metadata"] is None
