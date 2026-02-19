"""Guards for bd-3g1g.2.2 scope/capability claim model contract."""

from pathlib import Path
import re


ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "exec-plans"
    / "completed"
    / "bd-3g1g"
    / "bd-3g1g.2.2-scope-capability-claim-model.md"
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


def _extract_section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.find(start_heading)
    assert start >= 0, f"Missing section heading: {start_heading}"

    end = text.find(end_heading, start)
    assert end >= 0, f"Missing section heading: {end_heading}"
    return text[start:end]


def test_scope_claim_model_artifact_exists() -> None:
    assert ARTIFACT.exists(), "Expected bd-3g1g.2.2 artifact is missing"


def test_claim_envelope_required_fields_are_exact() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, "## Claim Envelope (normative)")
    assert len(rows) == 6, f"Expected 6 claim-envelope fields, found {len(rows)}"

    actual_fields = {row[0].strip("`") for row in rows}
    expected_fields = {
        "request_id",
        "workspace_id",
        "actor",
        "capability_claims",
        "cwd_or_worktree",
        "session_id",
    }
    assert actual_fields == expected_fields, "Claim envelope fields do not match expected contract set"
    assert len(actual_fields) == len(rows), "Duplicate claim envelope fields detected"


def test_capability_claim_registry_is_exact_phase1_baseline() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, "## Capability Claim Registry (phase-1 baseline)")
    assert len(rows) == 6, f"Expected 6 capability claim rows, found {len(rows)}"

    mapping = {(row[0].strip("`"), row[1].strip("`")) for row in rows}
    expected = {
        ("workspace.files.read", "workspace-core"),
        ("workspace.files.write", "workspace-core"),
        ("workspace.git.read", "workspace-core"),
        ("workspace.git.write", "workspace-core"),
        ("pty.session.start", "pty-service"),
        ("pty.session.attach", "pty-service"),
    }
    assert mapping == expected, "Capability claim registry does not match expected phase-1 baseline"
    assert len(mapping) == len(rows), "Duplicate capability claim rows detected"


def test_workspace_core_and_pty_service_have_explicit_deny_by_default_rules() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")

    workspace_section = _extract_section(
        text,
        "### `workspace-core` rules (normative)",
        "### `pty-service` rules (normative)",
    )
    pty_section = _extract_section(
        text,
        "### `pty-service` rules (normative)",
        "## Required Denial Outcomes",
    )

    workspace_required_terms = [
        "reject requests when `workspace_id` is absent or does not match",
        "require explicit write claims; read-only claims are insufficient",
        "claims are missing, malformed, empty, or unknown",
        "performs no side effects",
        "Validation runs before filesystem/git execution",
    ]
    for term in workspace_required_terms:
        assert term in workspace_section, f"Missing workspace-core deny-by-default rule term: {term}"

    pty_required_terms = [
        "reject requests when `workspace_id` is absent or mismatched",
        "PTY start/create requires `pty.session.start`",
        "PTY attach/stream requires `pty.session.attach` and a valid `session_id`",
        "Unknown claims, empty claim sets, or malformed claim payloads are denied",
        "Internal callers",
    ]
    for term in pty_required_terms:
        assert term in pty_section, f"Missing pty-service deny-by-default rule term: {term}"


def test_required_denial_outcomes_and_machine_codes_are_present() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    required_terms = [
        "MUST deny by default",
        "claim envelope is missing required fields",
        "`capability_claims` is empty",
        "required operation claim is absent",
        "claim value is unknown/malformed",
        "workspace/session scope does not match the target operation",
        "`invalid_scope_context`",
        "`capability_denied`",
        "`workspace_mismatch`",
        "`session_mismatch`",
    ]
    for term in required_terms:
        assert term in text, f"Missing denial outcome contract term: {term}"


def test_acceptance_confirmation_mentions_both_owner_services() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    assert "## Acceptance Confirmation" in text
    assert "`workspace-core` deny-by-default validation is explicitly defined" in text
    assert "`pty-service` deny-by-default validation is explicitly defined" in text
