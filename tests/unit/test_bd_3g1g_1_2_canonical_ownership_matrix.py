"""Validation checks for bd-3g1g.1.2 canonical ownership matrix artifact."""

from pathlib import Path
import re


INVENTORY_ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "ROUTE_CALLSITE_INVENTORY_bd-3g1g.1.1.md"
)
MATRIX_ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "bd-3g1g.1.2-canonical-ownership-matrix.md"
)

ALLOWED_OWNERS = {
    "front",
    "workspace-core",
    "pty-service",
    "agent-normal",
    "agent-companion",
    "agent-pi",
    "control-plane",
}
ALLOWED_STATUSES = {"canonical", "legacy", "dead"}
ALLOWED_ACTIONS = {"keep", "rewrite", "remove", "delegate"}


def _parse_inventory_route_families(text: str) -> list[str]:
    marker = "## Route Family Ledger (Unique Families)"
    assert marker in text, "Inventory missing route family ledger section"

    ledger_block = text.split(marker, maxsplit=1)[1]
    ledger_block = ledger_block.split("Status summary:", maxsplit=1)[0]

    families: list[str] = []
    for line in ledger_block.splitlines():
        match = re.match(r"^\s*\d+\.\s+`([^`]+)`\s*$", line)
        if match:
            families.append(match.group(1))
    return families


def _parse_matrix_rows(text: str) -> dict[str, dict[str, str]]:
    marker = "## Ownership Matrix"
    assert marker in text, "Matrix artifact missing Ownership Matrix section"
    block = text.split(marker, maxsplit=1)[1]

    rows: dict[str, dict[str, str]] = {}
    for line in block.splitlines():
        if not line.startswith("|"):
            continue
        cols = [col.strip() for col in line.split("|")]
        if len(cols) < 8:
            continue

        current = cols[1]
        target = cols[2]
        owner = cols[3]
        status = cols[4]
        action = cols[5]
        policy = cols[6]

        if current.lower() == "current family":
            continue
        if set(current) <= {"-", ":"}:
            continue

        current = current.strip("`")
        rows[current] = {
            "target": target.strip("`"),
            "owner": owner.strip("`"),
            "status": status.strip("`"),
            "action": action.strip("`"),
            "policy": policy,
        }

    return rows


def test_artifacts_exist() -> None:
    assert INVENTORY_ARTIFACT.exists(), "Expected bd-3g1g.1.1 inventory artifact is missing"
    assert MATRIX_ARTIFACT.exists(), "Expected bd-3g1g.1.2 matrix artifact is missing"


def test_matrix_covers_all_inventory_route_families() -> None:
    inventory_text = INVENTORY_ARTIFACT.read_text(encoding="utf-8")
    matrix_text = MATRIX_ARTIFACT.read_text(encoding="utf-8")

    inventory_families = _parse_inventory_route_families(inventory_text)
    matrix_rows = _parse_matrix_rows(matrix_text)

    assert len(inventory_families) == len(set(inventory_families)), (
        "Inventory route family ledger should contain unique families"
    )
    assert len(matrix_rows) == len(set(matrix_rows)), "Matrix should not contain duplicate current families"

    missing = sorted(set(inventory_families) - set(matrix_rows))
    assert not missing, "Matrix missing inventory route families:\n- " + "\n- ".join(missing)

    unexpected = sorted(set(matrix_rows) - set(inventory_families))
    assert not unexpected, "Matrix has unexpected route families:\n- " + "\n- ".join(unexpected)


def test_matrix_rows_are_execution_ready() -> None:
    matrix_text = MATRIX_ARTIFACT.read_text(encoding="utf-8")
    matrix_rows = _parse_matrix_rows(matrix_text)
    assert matrix_rows, "Expected at least one matrix row"

    for family, row in matrix_rows.items():
        target = row["target"].strip()
        owner = row["owner"].strip()
        status = row["status"].strip()
        action = row["action"].strip()
        policy = row["policy"].strip()

        assert target, f"Missing canonical target for {family}"
        assert owner in ALLOWED_OWNERS, f"Invalid owner for {family}: {owner}"
        assert status in ALLOWED_STATUSES, f"Invalid route status for {family}: {status}"
        assert action in ALLOWED_ACTIONS, f"Invalid migration action for {family}: {action}"
        assert policy, f"Missing policy notes for {family}"

        if status == "legacy":
            assert action in {"rewrite", "remove", "delegate"}, (
                f"Legacy family should not use keep action: {family}"
            )
        if status == "dead":
            assert action == "remove", f"Dead family should have remove action: {family}"
