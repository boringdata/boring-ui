"""Validation checks for bd-3g1g phase-1 contract freeze artifact."""

from pathlib import Path
import re


ARTIFACT = Path(__file__).resolve().parents[2] / "docs" / "bd-3g1g-phase1-contract-freeze.md"


def _extract_table_rows(text: str, heading: str) -> list[list[str]]:
    marker = f"\n{heading}\n"
    start = text.find(marker)
    assert start != -1, f"Missing section heading: {heading}"
    tail = text[start + len(marker):]

    # stop at the next markdown heading or end-of-file
    end_match = re.search(r"\n#{2,6}\s", tail)
    section = tail[: end_match.start()] if end_match else tail

    rows: list[list[str]] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        # skip separator rows like |---|---|
        if cells and all(cell and set(cell) <= {"-"} for cell in cells):
            continue
        rows.append(cells)

    # skip header row
    assert rows, f"No table rows found for section: {heading}"
    return rows[1:]


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

    rows = _extract_table_rows(text, "### Service ownership prefixes (normative)")
    assert len(rows) == 6, f"Expected exactly 6 canonical service-prefix rows, found {len(rows)}"

    # columns: service, http_prefix, ws_prefix, notes
    normalized = {
        (row[0], row[1], row[2])
        for row in rows
    }
    expected = {
        ("`workspace-core`", "`/api/v1/files/*`, `/api/v1/git/*`", "none"),
        ("`pty-service`", "`/api/v1/pty/*` (lifecycle metadata)", "`/ws/pty`"),
        ("`agent-normal`", "`/api/v1/agent/normal/*`", "`/ws/agent/normal/*`"),
        ("`agent-companion`", "`/api/v1/agent/companion/*`", "`/ws/agent/companion/*`"),
        ("`agent-pi`", "`/api/v1/agent/pi/*`", "`/ws/agent/pi/*`"),
        ("`control-plane` (frontend callable)", "`/auth/*`, `/api/v1/me`, `/api/v1/workspaces*`, `/w/{workspace_id}/*`", "`/w/{workspace_id}/{path}`"),
    }
    assert normalized == expected, "Canonical service-prefix table does not match expected exact contract set"
    assert len(rows) == len(normalized), "Duplicate rows detected in canonical service-prefix table"

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
    rows = _extract_table_rows(text, "## Mutation Semantics Freeze")
    mapping = {row[0]: (row[1], row[2]) for row in rows}

    assert "create/queue (`POST`)" in mapping
    assert "idempotency key required" in mapping["create/queue (`POST`)"][0]
    assert "duplicate key returns existing operation outcome" in mapping["create/queue (`POST`)"][1]

    assert "write/rename/move/delete" in mapping
    assert "retries must not produce duplicated side effects" in mapping["write/rename/move/delete"][0]
    assert "deterministic conflict/forbidden envelope" in mapping["write/rename/move/delete"][1]

    assert "runtime retry/start" in mapping
    assert "dedupe per workspace/session" in mapping["runtime retry/start"][0]
    assert "concurrent in-flight operation returns conflict envelope" in mapping["runtime retry/start"][1]
