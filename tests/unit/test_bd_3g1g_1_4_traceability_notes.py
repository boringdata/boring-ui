"""Validation checks for bd-3g1g.1.4 traceability notes artifact."""

import json
import re
from pathlib import Path


ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "bd-3g1g.1.4-traceability-notes.md"
)
ISSUES = Path(__file__).resolve().parents[2] / ".beads" / "issues.jsonl"

TABLE_HEADING = "## Bead Traceability Matrix (Phase + Subtask)"


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


def _expected_traceability_ids() -> list[str]:
    expected: list[str] = []
    pattern = re.compile(r"^bd-3g1g(?:\.[0-9]+){1,2}$")

    for line in ISSUES.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        obj = json.loads(raw)
        bead_id = obj.get("id", "")
        if isinstance(bead_id, str) and pattern.fullmatch(bead_id):
            expected.append(bead_id)

    expected_sorted = sorted(set(expected), key=lambda value: [int(part) for part in value.split(".")[1:]])
    return expected_sorted


def test_traceability_artifact_exists() -> None:
    assert ARTIFACT.exists(), "Expected bd-3g1g.1.4 traceability artifact is missing"
    assert ISSUES.exists(), "Expected beads issues jsonl is missing"


def test_traceability_notes_cover_all_phase_and_subtask_beads() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, TABLE_HEADING)

    actual_ids = [row[0].strip("`") for row in rows]
    expected_ids = _expected_traceability_ids()

    assert len(actual_ids) == len(set(actual_ids)), "Duplicate bead IDs in traceability matrix"
    assert set(actual_ids) == set(expected_ids), (
        "Traceability matrix bead coverage mismatch.\n"
        f"Missing: {sorted(set(expected_ids) - set(actual_ids))}\n"
        f"Unexpected: {sorted(set(actual_ids) - set(expected_ids))}"
    )


def test_traceability_rows_have_required_mapping_dimensions() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, TABLE_HEADING)

    assert rows, "Expected traceability rows"
    for row in rows:
        assert len(row) >= 8, f"Row has too few columns: {row}"

        bead_id = row[0].strip("`")
        why = row[1]
        goals = row[2]
        non_goals = row[3]
        arch_boundary = row[4]
        risks = row[5]
        verification = row[6]
        evidence = row[7]

        assert why, f"Missing rationale text for {bead_id}"
        assert re.search(r"\bG[1-4]\b", goals), f"Missing goal reference for {bead_id}"
        assert re.search(r"\bN[1-3]\b", non_goals), f"Missing non-goal reference for {bead_id}"
        assert re.search(r"\bAR[1-8]\b", arch_boundary), f"Missing architecture rule reference for {bead_id}"
        assert re.search(r"\bSB[1-6]\b", arch_boundary), f"Missing service boundary reference for {bead_id}"
        assert re.search(r"\bR[1-4]\b", risks), f"Missing risk reference for {bead_id}"
        assert re.search(r"\bVM[1-6]\b", verification), f"Missing verification-matrix reference for {bead_id}"
        assert evidence and ".evidence/" in evidence, f"Missing evidence linkage for {bead_id}"


def test_phase_rows_define_concrete_evidence_expectations() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, TABLE_HEADING)
    row_map = {row[0].strip("`"): row for row in rows}

    phase_ids = [f"bd-3g1g.{phase}" for phase in range(1, 8)]
    for phase_id in phase_ids:
        assert phase_id in row_map, f"Missing phase bead row: {phase_id}"
        evidence = row_map[phase_id][7].lower()
        for token in ("unit", "integration", "e2e", "logging"):
            assert token in evidence, f"Phase row {phase_id} missing evidence expectation token: {token}"


def test_traceability_notes_cover_major_plan_dimensions() -> None:
    text = ARTIFACT.read_text(encoding="utf-8")
    required_terms = [
        "## Reference Legend",
        "Goals (`## Goals`)",
        "Non-goals (`## Non-Goals (This Plan)`)",
        "Architecture rules (`## Architecture Rules`)",
        "Service boundaries (`## Service Boundaries` + boundary enforcement)",
        "Risks (`## Risks and Mitigations`)",
        "Verification matrix (`## Verification Matrix`)",
    ]
    for term in required_terms:
        assert term in text, f"Missing major plan traceability section: {term}"
