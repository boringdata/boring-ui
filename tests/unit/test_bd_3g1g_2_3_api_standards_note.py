"""Validation checks for bd-3g1g.2.3 API standards note artifact."""

from pathlib import Path
import re


ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "bd-3g1g.2.3-api-standards-note.md"
)
PLAN_ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "SERVICE_SPLIT_AND_LEGACY_CLEANUP_PLAN.md"
)
PHASE1_ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "bd-3g1g-phase1-contract-freeze.md"
)


def _extract_table_rows(text: str, heading: str) -> list[list[str]]:
    marker = f"\n{heading}\n"
    start = text.find(marker)
    assert start != -1, f"Missing section heading: {heading}"
    tail = text[start + len(marker):]

    end_match = re.search(r"\n#{2,6}\s", tail)
    section = tail[: end_match.start()] if end_match else tail

    rows: list[list[str]] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)

    assert rows, f"No table rows found for section: {heading}"
    return rows[1:]


def test_api_standards_artifacts_exist() -> None:
    assert ARTIFACT.exists(), "Expected bd-3g1g.2.3 standards artifact is missing"
    assert PLAN_ARTIFACT.exists(), "Expected service split plan artifact is missing"
    assert PHASE1_ARTIFACT.exists(), "Expected phase-1 freeze artifact is missing"


def test_api_standards_note_has_required_error_envelope_contract() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    required_terms = [
        '"code": "string_machine_code"',
        '"message": "human readable summary"',
        '"retryable": false',
        '"details"',
        '"request_id"',
        '"workspace_id"',
    ]
    for term in required_terms:
        assert term in text, f"Missing required error envelope term: {term}"


def test_api_standards_note_has_exact_error_code_baseline() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, "## Standard Error Code Set (phase-1 baseline)")
    assert len(rows) == 7, f"Expected 7 error code rows, found {len(rows)}"

    actual_codes = {row[0].strip("`") for row in rows}
    expected_codes = {
        "invalid_scope_context",
        "workspace_mismatch",
        "session_mismatch",
        "capability_denied",
        "conflict_in_flight",
        "idempotency_replay",
        "upstream_unavailable",
    }
    assert actual_codes == expected_codes, "Error code baseline does not match expected contract set"
    assert len(actual_codes) == len(rows), "Duplicate error code rows detected"


def test_api_standards_note_has_exact_mutation_contract_rows() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, "## Mutation Semantics (normative)")
    assert len(rows) == 3, f"Expected 3 mutation contract rows, found {len(rows)}"

    operations = {row[0] for row in rows}
    expected = {
        "create/queue (`POST`)",
        "write/rename/move/delete",
        "runtime retry/start",
    }
    assert operations == expected, "Mutation operation class set does not match expected contract"
    assert len(operations) == len(rows), "Duplicate mutation operation rows detected"


def test_api_standards_note_has_service_adoption_for_all_owners() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, "## Service Adoption Matrix")
    assert len(rows) == 5, f"Expected 5 service adoption rows, found {len(rows)}"

    services = {row[0].strip("`") for row in rows}
    expected_services = {
        "workspace-core",
        "pty-service",
        "agent-normal",
        "agent-companion",
        "agent-pi",
    }
    assert services == expected_services, "Service adoption matrix does not cover expected owners"


def test_service_contract_docs_reference_api_standards_note() -> None:
    standards_path = "docs/bd-3g1g.2.3-api-standards-note.md"
    plan_text = PLAN_ARTIFACT.read_text(encoding="utf-8")
    phase1_text = PHASE1_ARTIFACT.read_text(encoding="utf-8")

    assert standards_path in plan_text, "Service split plan does not reference bd-3g1g.2.3 standards note"
    assert phase1_text.count(standards_path) >= 2, (
        "Phase-1 freeze should reference bd-3g1g.2.3 standards note for both error and mutation sections"
    )
