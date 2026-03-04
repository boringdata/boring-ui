"""Guards for boring-ui core ownership contract baseline (bd-2ptn)."""

from pathlib import Path


CONTRACT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "exec-plans"
    / "backlog"
    / "boring-ui-core-ownership-contract.md"
)


def test_contract_exists() -> None:
    assert CONTRACT.exists(), f"Missing ownership contract: {CONTRACT}"


def test_contract_has_required_route_ownership_terms() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    required_terms = [
        "/auth/*",
        "/api/v1/me",
        "/api/v1/workspaces*",
        "/api/v1/workspaces/{id}/members*",
        "/api/v1/workspaces/{id}/invites*",
        "/api/v1/files/*",
        "/api/v1/git/*",
        "/api/v1/macro/*",
        "boring-sandbox",
        "edge-only",
        "No retro compatibility for legacy sandbox sessions/data",
    ]
    for term in required_terms:
        assert term in text, f"Missing ownership term: {term}"


def test_contract_has_keep_vs_move_and_modes() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    assert "## Keep vs Move (boring-sandbox)" in text
    assert "### Stays in `boring-sandbox`" in text
    assert "### Moves to `boring-ui` core" in text
    assert "## Deployment Modes" in text
    assert "Core mode (single backend)" in text
    assert "Proxy mode" in text
