"""Coverage guard for bd-3g1g.1.1 route/callsite inventory artifact."""

from pathlib import Path


INVENTORY_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs/ROUTE_CALLSITE_INVENTORY_bd-3g1g.1.1.md"
)

REQUIRED_FAMILIES = [
    "/api/v1/files/list",
    "/api/v1/files/read",
    "/api/v1/files/write",
    "/api/v1/files/delete",
    "/api/v1/files/rename",
    "/api/v1/files/move",
    "/api/v1/files/search",
    "/api/v1/git/status",
    "/api/v1/git/diff",
    "/api/v1/git/show",
    "/api/capabilities",
    "/api/project",
    "/api/sessions",
    "/api/approval/request",
    "/ws/pty",
    "/ws/claude-stream",
    "/api/x/{plugin}/...",
    "/ws/plugins",
    "/api/tree",
    "/api/file",
    "/api/file/rename",
    "/api/file/move",
    "/api/search",
    "/api/git/status",
    "/api/attachments",
    "/api/fs/{list,home}",
    "/api/envs{,/{slug}}",
    "/ws/browser/{session_id}",
    "/api/sessions/create",
    "/api/sessions/{id}/history",
    "/api/sessions/{id}/stream",
    "/api/v1/me",
    "/api/v1/workspaces",
    "/auth/logout",
    "/w/{workspace_id}/{path}",
    "/api/v1/agent/normal/*",
    "/api/v1/agent/companion/*",
    "/api/v1/agent/pi/*",
]

REQUIRED_TAGS = [
    "canonical-live",
    "dynamic-plugin-optional",
    "legacy-callsite",
    "legacy-unmounted-backend",
    "control-plane-canonical-doc",
    "external-service-live",
    "unknown-missing",
]


def test_inventory_artifact_exists() -> None:
    assert INVENTORY_PATH.exists(), f"Missing inventory artifact: {INVENTORY_PATH}"


def test_inventory_includes_required_route_families_and_tags() -> None:
    text = INVENTORY_PATH.read_text(encoding="utf-8")

    missing_families = [family for family in REQUIRED_FAMILIES if family not in text]
    assert not missing_families, (
        "Inventory is missing required route families:\n- "
        + "\n- ".join(missing_families)
    )

    missing_tags = [tag for tag in REQUIRED_TAGS if tag not in text]
    assert not missing_tags, (
        "Inventory is missing required category tags:\n- "
        + "\n- ".join(missing_tags)
    )
