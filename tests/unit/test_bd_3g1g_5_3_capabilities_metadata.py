"""Guards for bd-3g1g.5.3 capabilities/registry metadata alignment.

This bead aligns router/capability metadata with the service-ownership split
without changing the /api/capabilities response schema (no new keys).
"""

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


def test_capabilities_router_descriptions_encode_owner_and_canonical_contract() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/capabilities")
    assert response.status_code == 200
    payload = response.json()

    by_name = _routers_by_name(payload)

    # Assert no new schema keys were added for this bead.
    sample = by_name["files"]
    assert "owner_service" not in sample
    assert "canonical_families" not in sample
    assert "contract_metadata" not in sample
    assert "contract_metadata_included" not in sample

    # Ownership markers (machine-checkable) embedded in existing description field.
    assert by_name["files"]["description"].startswith("[owner=workspace-core] [canonical=/api/v1/files/*] ")
    assert by_name["git"]["description"].startswith("[owner=workspace-core] [canonical=/api/v1/git/*] ")
    assert by_name["pty"]["description"].startswith("[owner=pty-service] [canonical=/ws/pty] ")
    assert by_name["chat_claude_code"]["description"].startswith("[owner=agent-normal] [canonical=/ws/claude-stream] ")
    assert by_name["approval"]["description"].startswith("[owner=boring-ui] [canonical=/api/approval/*] ")

