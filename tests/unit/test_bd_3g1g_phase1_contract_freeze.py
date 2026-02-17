"""Validation checks for bd-3g1g phase-1 contract freeze artifact."""

from pathlib import Path


ARTIFACT = Path(__file__).resolve().parents[2] / "docs" / "bd-3g1g-phase1-contract-freeze.md"


def test_phase1_contract_freeze_artifact_exists() -> None:
    assert ARTIFACT.exists(), "Expected phase-1 contract freeze artifact is missing"


def test_phase1_contract_freeze_has_required_prefixes() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    required_prefixes = [
        "/api/v1/files/*",
        "/api/v1/git/*",
        "/api/v1/pty/*",
        "/ws/pty",
        "/api/v1/agent/normal/*",
        "/api/v1/agent/companion/*",
        "/api/v1/agent/pi/*",
        "/ws/agent/normal/*",
        "/ws/agent/companion/*",
        "/ws/agent/pi/*",
        "/api/v1/me",
        "/api/v1/workspaces*",
        "/auth/*",
        "/w/{workspace_id}/*",
    ]
    for prefix in required_prefixes:
        assert prefix in text, f"Missing canonical prefix contract: {prefix}"


def test_phase1_contract_freeze_has_scope_and_error_contracts() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    required_terms = [
        "request_id",
        "workspace_id",
        "session_id",
        "capability_claims",
        '"code": "string_machine_code"',
        '"message": "human readable summary"',
        '"retryable": false',
        '"details"',
    ]
    for term in required_terms:
        assert term in text, f"Missing required scope/error contract term: {term}"


def test_phase1_contract_freeze_has_exit_gate_checklist() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    assert "Exit-gate checklist for `bd-3g1g.2`" in text
    assert "canonical prefixes are explicitly frozen." in text
    assert "error envelope and mutation semantics are explicitly defined." in text
