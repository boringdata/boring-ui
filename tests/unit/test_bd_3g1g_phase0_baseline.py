"""Validation checks for bd-3g1g phase-0 baseline artifact."""

from pathlib import Path
import re


ARTIFACT = Path(__file__).resolve().parents[2] / "docs" / "bd-3g1g-phase0-baseline.md"


def test_phase0_baseline_artifact_exists() -> None:
    assert ARTIFACT.exists(), "Expected phase-0 baseline artifact is missing"


def test_phase0_baseline_has_required_route_families() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")

    required_families = [
        "/api/v1/files/*",
        "/api/v1/git/*",
        "/ws/pty",
        "/ws/claude-stream",
        "/api/capabilities",
        "/api/tree",
        "/api/file",
        "/api/search",
        "/api/attachments",
        "/api/v1/me",
        "/api/v1/workspaces*",
        "/auth/logout",
        "/w/{workspace_id}/*",
    ]

    for family in required_families:
        assert family in text, f"Missing required route family: {family}"


def test_phase0_baseline_has_no_unclassified_routes() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    assert "unclassified" not in text.lower()

    statuses = re.findall(r"\|\s*(canonical|legacy|dead)\s*\|", text)
    assert statuses, "Expected classified status values in ownership matrix"
    assert set(statuses) <= {"canonical", "legacy", "dead"}


def test_phase0_baseline_covers_phase_gate_ids() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")

    required_ids = [
        "bd-3g1g.1",
        "bd-3g1g.1.1",
        "bd-3g1g.1.2",
        "bd-3g1g.1.3",
        "bd-3g1g.1.4",
        "bd-3g1g.2",
        "bd-3g1g.3",
        "bd-3g1g.4",
        "bd-3g1g.5",
        "bd-3g1g.6",
        "bd-3g1g.7",
    ]

    for bead_id in required_ids:
        assert bead_id in text, f"Missing required bead id in baseline: {bead_id}"
