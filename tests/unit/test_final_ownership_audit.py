"""Final ownership audit guardrails for sandbox cleanup tracking (bd-13yb)."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OWNERSHIP_AUDIT = REPO_ROOT / "docs" / "references" / "OWNERSHIP_AUDIT.md"


def test_final_audit_doc_exists_with_route_family_matrix() -> None:
    text = OWNERSHIP_AUDIT.read_text(encoding="utf-8")
    required_families = (
        "/auth/*",
        "/api/v1/me*",
        "/api/v1/workspaces*",
        "/api/v1/files*",
        "/api/v1/git*",
        "/api/v1/macro/*",
    )
    for family in required_families:
        assert family in text
    assert "edge proxy/routing/provisioning/token injection" in text


def test_final_audit_doc_defines_module_level_split() -> None:
    text = OWNERSHIP_AUDIT.read_text(encoding="utf-8")
    assert "Module-Level Ownership" in text
    assert "auth/session" in text
    assert "user/workspace/membership/invite/settings" in text
    assert "files/git business logic and policy checks" in text
    assert "edge ingress/routing/provisioning/header injection" in text


def test_sandbox_cleanup_checklist_tracks_required_cleanup_actions() -> None:
    text = OWNERSHIP_AUDIT.read_text(encoding="utf-8")
    required_items = (
        "duplicate auth/session business logic from `boring-sandbox`",
        "duplicate user/workspace/membership/invite/settings business logic from `boring-sandbox`",
        "duplicate filesystem/git policy/business logic from `boring-sandbox`",
        "workspace API behavior as pass-through",
        "single source of truth for workspace/user management",
    )
    for item in required_items:
        assert item in text
