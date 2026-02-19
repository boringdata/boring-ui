"""Coverage guard for bd-3g1g.1.1 route/callsite inventory artifact."""

from pathlib import Path
from collections import Counter
import re


INVENTORY_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "exec-plans"
    / "completed"
    / "bd-3g1g"
    / "ROUTE_CALLSITE_INVENTORY_bd-3g1g.1.1.md"
)

EXPECTED_LEDGER_FAMILIES = [
    "/health",
    "/api/capabilities",
    "/api/config",
    "/api/project",
    "/api/sessions",
    "/api/approval/request",
    "/api/approval/pending",
    "/api/approval/decision",
    "/api/approval/status/{request_id}",
    "/api/approval/{request_id}",
    "/api/v1/files/list",
    "/api/v1/files/read",
    "/api/v1/files/write",
    "/api/v1/files/delete",
    "/api/v1/files/rename",
    "/api/v1/files/move",
    "/api/v1/files/search",
    "/api/v1/git/status",
    "/api/v1/git/diff",
    "/api/v1/git/show",
    "/ws/pty",
    "/ws/claude-stream",
    "/api/x/{plugin}/...",
    "/ws/plugins",
    "/api/tree",
    "/api/file",
    "/api/file/rename",
    "/api/file/move",
    "/api/search",
    "/api/git/status",
    "/api/git/diff",
    "/api/git/show",
    "/api/attachments",
    "/api/fs/{list,home}",
    "/api/envs{,/{slug}}",
    "/api/git/{repo-info,branches,worktrees,worktree,fetch,pull}",
    "/ws/browser/{session_id}",
    "/api/sessions/create",
    "/api/sessions/{id}/history",
    "/api/sessions/{id}/stream",
    "/api/v1/me",
    "/api/v1/workspaces",
    "/api/v1/workspaces/{workspace_id}/runtime",
    "/api/v1/workspaces/{workspace_id}/runtime/retry",
    "/api/v1/workspaces/{workspace_id}/settings",
    "/auth/login",
    "/auth/callback",
    "/auth/logout",
    "/w/{workspace_id}/setup",
    "/w/{workspace_id}/{path}",
    "/api/v1/agent/normal/*",
    "/api/v1/agent/companion/*",
    "/api/v1/agent/pi/*",
]

REQUIRED_TAGS = [
    "canonical-live",
    "dynamic-plugin-optional",
    "legacy-callsite",
    "legacy-unmounted-backend",
    "control-plane-canonical-doc",
    "external-service-live",
    "unknown-missing",
]


def test_inventory_artifact_exists() -> None:
    assert INVENTORY_PATH.exists(), f"Missing inventory artifact: {INVENTORY_PATH}"


def test_inventory_includes_required_route_families_and_tags() -> None:
    text = INVENTORY_PATH.read_text(encoding="utf-8")

    marker = "## Route Family Ledger (Unique Families)"
    assert marker in text, "Inventory is missing the route family ledger section"

    ledger_block = text.split(marker, maxsplit=1)[1]
    ledger_block = ledger_block.split("Status summary:", maxsplit=1)[0]

    found_families = []
    for line in ledger_block.splitlines():
        match = re.match(r"^\s*\d+\.\s+`([^`]+)`\s*$", line)
        if match:
            found_families.append(match.group(1))

    expected_counts = Counter(EXPECTED_LEDGER_FAMILIES)
    found_counts = Counter(found_families)

    missing_families = sorted(set(expected_counts) - set(found_counts))
    assert not missing_families, (
        "Inventory is missing route families:\n- " + "\n- ".join(missing_families)
    )

    unexpected_families = sorted(set(found_counts) - set(expected_counts))
    assert not unexpected_families, (
        "Inventory contains unexpected route families:\n- " + "\n- ".join(unexpected_families)
    )

    duplicate_families = sorted(
        family for family, count in found_counts.items() if count != expected_counts.get(family, 0)
    )
    assert not duplicate_families, (
        "Inventory has duplicate/mismatched family counts:\n- "
        + "\n- ".join(
            f"{family}: expected {expected_counts.get(family, 0)}, found {found_counts[family]}"
            for family in duplicate_families
        )
    )

    parsed_tags = set()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cols = [col.strip() for col in line.split("|")]
        if len(cols) < 5:
            continue
        tag_col = cols[3].strip()
        if not tag_col:
            continue
        if tag_col.lower() == "tag(s)":
            continue
        if set(tag_col) == {"-"}:
            continue
        tag_col = tag_col.replace("`", "")
        for tag in [token.strip() for token in tag_col.split(",")]:
            if tag:
                parsed_tags.add(tag)

    missing_tags = [tag for tag in REQUIRED_TAGS if tag not in parsed_tags]
    assert not missing_tags, (
        "Inventory is missing required category tags:\n- "
        + "\n- ".join(missing_tags)
    )
