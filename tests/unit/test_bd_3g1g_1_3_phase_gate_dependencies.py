"""Validation checks for bd-3g1g.1.3 phase-gate dependency graph."""

from pathlib import Path
import json


GRAPH_ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "bd-3g1g.1.3-phase-gate-dependency-graph.md"
)
ISSUES_JSONL = Path(__file__).resolve().parents[2] / ".beads" / "issues.jsonl"


def _load_dependency_index() -> dict[str, set[tuple[str, str]]]:
    index: dict[str, set[tuple[str, str]]] = {}
    with ISSUES_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            issue_id = record.get("id")
            if not isinstance(issue_id, str) or not issue_id.startswith("bd-3g1g"):
                continue
            deps = set()
            for dep in record.get("dependencies", []):
                dep_type = dep.get("type")
                depends_on = dep.get("depends_on_id")
                if isinstance(dep_type, str) and isinstance(depends_on, str):
                    deps.add((dep_type, depends_on))
            index[issue_id] = deps
    return index


def _assert_has_blocks_edge(
    index: dict[str, set[tuple[str, str]]], issue_id: str, depends_on_id: str
) -> None:
    assert issue_id in index, f"Missing issue in dependency index: {issue_id}"
    assert ("blocks", depends_on_id) in index[issue_id], (
        f"Expected blocks edge {issue_id} -> {depends_on_id} is missing"
    )


def test_phase_gate_graph_artifact_exists() -> None:
    assert GRAPH_ARTIFACT.exists(), "Expected phase-gate graph artifact is missing"


def test_phase_gate_graph_artifact_contains_required_sections() -> None:
    text = GRAPH_ARTIFACT.read_text(encoding="utf-8")
    required_tokens = [
        "## Gate Edges Added In This Bead",
        "## Phase-Level Dependency Graph",
        "## Critical Path (Tracker-Enforced)",
        "```mermaid",
        "bd-3g1g.3",
        "bd-3g1g.2.4",
        "bd-3g1g.5",
        "bd-3g1g.3.5",
        "bd-3g1g.6",
        "bd-3g1g.5.5",
    ]
    for token in required_tokens:
        assert token in text, f"Missing expected token in graph artifact: {token}"


def test_phase_gates_are_encoded_as_blocks_dependencies() -> None:
    index = _load_dependency_index()

    # Phase chain and newly encoded phase-gate edges.
    _assert_has_blocks_edge(index, "bd-3g1g.2", "bd-3g1g.1")
    _assert_has_blocks_edge(index, "bd-3g1g.3", "bd-3g1g.2")
    _assert_has_blocks_edge(index, "bd-3g1g.3", "bd-3g1g.2.4")
    _assert_has_blocks_edge(index, "bd-3g1g.4", "bd-3g1g.3")
    _assert_has_blocks_edge(index, "bd-3g1g.4", "bd-3g1g.3.4")
    _assert_has_blocks_edge(index, "bd-3g1g.5", "bd-3g1g.3")
    _assert_has_blocks_edge(index, "bd-3g1g.5", "bd-3g1g.3.5")
    _assert_has_blocks_edge(index, "bd-3g1g.6", "bd-3g1g.5")
    _assert_has_blocks_edge(index, "bd-3g1g.6", "bd-3g1g.5.5")
    _assert_has_blocks_edge(index, "bd-3g1g.7", "bd-3g1g.4")
    _assert_has_blocks_edge(index, "bd-3g1g.7", "bd-3g1g.6")

    # Phase-0 chain used as entry gate to later phases.
    _assert_has_blocks_edge(index, "bd-3g1g.1.2", "bd-3g1g.1.1")
    _assert_has_blocks_edge(index, "bd-3g1g.1.3", "bd-3g1g.1.2")
    _assert_has_blocks_edge(index, "bd-3g1g.1.4", "bd-3g1g.1.3")

    # Verification closeout chain.
    _assert_has_blocks_edge(index, "bd-3g1g.7.5", "bd-3g1g.3.4")
    _assert_has_blocks_edge(index, "bd-3g1g.7.5", "bd-3g1g.4.4")
    _assert_has_blocks_edge(index, "bd-3g1g.7.5", "bd-3g1g.5.4")
    _assert_has_blocks_edge(index, "bd-3g1g.7.5", "bd-3g1g.6.5")
    _assert_has_blocks_edge(index, "bd-3g1g.7.2", "bd-3g1g.7.1")
    _assert_has_blocks_edge(index, "bd-3g1g.7.2", "bd-3g1g.7.5")
    _assert_has_blocks_edge(index, "bd-3g1g.7.3", "bd-3g1g.7.2")
    _assert_has_blocks_edge(index, "bd-3g1g.7.4", "bd-3g1g.7.3")
