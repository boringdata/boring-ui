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
        "/w/{workspace_id}/{path}",
    ]
    for prefix in required_prefixes:
        assert prefix in text, f"Missing canonical prefix contract: {prefix}"


def test_phase1_contract_freeze_service_prefix_table_is_exact() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")

    expected_rows = [
        "| `workspace-core` | `/api/v1/files/*`, `/api/v1/git/*` | none |",
        "| `pty-service` | `/api/v1/pty/*` (lifecycle metadata) | `/ws/pty` |",
        "| `agent-normal` | `/api/v1/agent/normal/*` | `/ws/agent/normal/*` |",
        "| `agent-companion` | `/api/v1/agent/companion/*` | `/ws/agent/companion/*` |",
        "| `agent-pi` | `/api/v1/agent/pi/*` | `/ws/agent/pi/*` |",
        "| `control-plane` (frontend callable) | `/auth/*`, `/api/v1/me`, `/api/v1/workspaces*`, `/w/{workspace_id}/*` | `/w/{workspace_id}/{path}` |",
    ]
    for row in expected_rows:
        assert row in text, f"Missing or changed canonical service-prefix row: {row}"

    disallowed_legacy_rows = [
        "| `workspace-core` | `/api/tree` |",
        "| `workspace-core` | `/api/file` |",
        "| `workspace-core` | `/api/search` |",
        "| `workspace-core` | `/api/git/*` |",
    ]
    for legacy in disallowed_legacy_rows:
        assert legacy not in text, f"Legacy family leaked into canonical prefix freeze: {legacy}"


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


def test_phase1_contract_freeze_has_mutation_semantics_contracts() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    required_mutation_terms = [
        "create/queue (`POST`)",
        "write/rename/move/delete",
        "runtime retry/start",
        "idempotency key required",
        "duplicate key returns existing operation outcome",
        "concurrent in-flight operation returns conflict envelope",
    ]
    for term in required_mutation_terms:
        assert term in text, f"Missing mutation semantics term: {term}"
