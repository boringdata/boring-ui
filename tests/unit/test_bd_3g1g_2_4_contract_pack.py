"""Guards for bd-3g1g.2.4 contract pack and sign-off baseline."""

from pathlib import Path
import re


CONTRACT_PACK = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "bd-3g1g.2.4-contract-pack-v1.md"
)
SIGNOFF_RECORD = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "bd-3g1g.2.4-signoff.md"
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


def test_contract_pack_and_signoff_exist() -> None:
    assert CONTRACT_PACK.exists(), "Expected bd-3g1g.2.4 contract pack is missing"
    assert SIGNOFF_RECORD.exists(), "Expected bd-3g1g.2.4 sign-off record is missing"


def test_contract_pack_has_expected_metadata_and_lock_reference() -> None:
    text = CONTRACT_PACK.read_text(encoding="utf-8")
    required_terms = [
        "Bead: `bd-3g1g.2.4`",
        "Version: `v1.0.0`",
        "Published: `2026-02-17` (UTC)",
        "Status: locked by `docs/bd-3g1g.2.4-signoff.md`",
    ]
    for term in required_terms:
        assert term in text, f"Missing contract-pack metadata term: {term}"


def test_contract_pack_service_ownership_table_is_exact() -> None:
    text = CONTRACT_PACK.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, "## Canonical Service Ownership and Route Families")
    assert len(rows) == 6, f"Expected 6 service-ownership rows, found {len(rows)}"

    for row in rows:
        assert len(row) == 5, f"Expected 5 columns in service ownership row, found {len(row)}: {row}"

    actual = {(row[0], row[1], row[2], row[3], row[4]) for row in rows}
    expected = {
        (
            "`workspace-core`",
            "`/api/v1/files/*`, `/api/v1/git/*`",
            "none",
            "no",
            "deny by default on missing scope/claims",
        ),
        (
            "`pty-service`",
            "`/api/v1/pty/*`",
            "`/ws/pty`",
            "no",
            "deny by default on missing scope/claims/session",
        ),
        (
            "`agent-normal`",
            "`/api/v1/agent/normal/*`",
            "`/ws/agent/normal/*`",
            "no",
            "runtime/session authority only",
        ),
        (
            "`agent-companion`",
            "`/api/v1/agent/companion/*`",
            "`/ws/agent/companion/*`",
            "no",
            "runtime/session authority only",
        ),
        (
            "`agent-pi`",
            "`/api/v1/agent/pi/*`",
            "`/ws/agent/pi/*`",
            "no",
            "runtime/session authority only",
        ),
        (
            "`control-plane`",
            "`/auth/*`, `/api/v1/me`, `/api/v1/workspaces*`, `/w/{workspace_id}/*`",
            "`/w/{workspace_id}/{path}`",
            "yes",
            "sole frontend boundary for auth + membership + policy",
        ),
    }
    assert actual == expected, "Service ownership table does not match locked contract baseline"


def test_frontend_control_plane_contract_only_lists_allowed_direct_routes() -> None:
    text = CONTRACT_PACK.read_text(encoding="utf-8")
    rows = _extract_table_rows(text, "## Frontend -> Control-Plane Contract (Only Direct UI Surface)")

    for row in rows:
        assert len(row) == 3, f"Expected 3 columns in frontend contract row, found {len(row)}: {row}"

    actual_method_path = {(row[0], row[1]) for row in rows}
    expected_method_path = {
        ("`GET`", "`/auth/login`"),
        ("`GET`", "`/auth/callback`"),
        ("`GET`", "`/auth/logout`"),
        ("`GET`", "`/api/v1/me`"),
        ("`GET`", "`/api/v1/workspaces`"),
        ("`POST`", "`/api/v1/workspaces`"),
        ("`GET`", "`/api/v1/workspaces/{workspace_id}/runtime`"),
        ("`POST`", "`/api/v1/workspaces/{workspace_id}/runtime/retry`"),
        ("`GET`", "`/api/v1/workspaces/{workspace_id}/settings`"),
        ("`PUT`", "`/api/v1/workspaces/{workspace_id}/settings`"),
        ("`GET`", "`/w/{workspace_id}/setup`"),
        ("`GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS`", "`/w/{workspace_id}/{path}`"),
        ("`WS`", "`/w/{workspace_id}/{path}`"),
    }
    assert actual_method_path == expected_method_path, (
        "Frontend control-plane direct route contract does not match locked method+path baseline"
    )

    forbidden_direct_paths = {
        "`/api/v1/files/*`",
        "`/api/v1/git/*`",
        "`/api/v1/pty/*`",
        "`/api/v1/agent/normal/*`",
        "`/api/v1/agent/companion/*`",
        "`/api/v1/agent/pi/*`",
    }
    paths = {row[1] for row in rows}
    leaked = sorted(forbidden_direct_paths & paths)
    assert not leaked, "Internal service routes leaked into frontend direct contract:\n- " + "\n- ".join(leaked)


def test_contract_pack_has_precedence_and_not_frontend_callable_guards() -> None:
    text = CONTRACT_PACK.read_text(encoding="utf-8")

    required_precedence_terms = [
        "Control-plane explicit subpaths are matched first",
        "workspace-scoped proxy targets and must enforce session + membership policy",
        "unmatched/forbidden subpaths are denied by default",
    ]
    for term in required_precedence_terms:
        assert term in text, f"Missing route precedence contract term: {term}"

    rows = _extract_table_rows(text, "## Not Frontend-Callable Directly")
    families = {row[0].strip("`") for row in rows}
    expected_families = {
        "/api/v1/files/*",
        "/api/v1/git/*",
        "/api/v1/pty/*",
        "/ws/pty",
        "/api/v1/agent/normal/*",
        "/ws/agent/normal/*",
        "/api/v1/agent/companion/*",
        "/ws/agent/companion/*",
        "/api/v1/agent/pi/*",
        "/ws/agent/pi/*",
        "legacy direct `/api/*` and `/ws/*` without workspace scope",
    }
    assert families == expected_families, "Not-frontend-callable family set is incomplete or changed"


def test_contract_pack_has_scope_claim_and_error_semantics_baseline() -> None:
    text = CONTRACT_PACK.read_text(encoding="utf-8")

    required_terms = [
        "`request_id`",
        "`workspace_id`",
        "`actor`",
        "`capability_claims`",
        "`cwd_or_worktree`",
        "`session_id`",
        "`workspace.files.read`",
        "`workspace.files.write`",
        "`workspace.git.read`",
        "`workspace.git.write`",
        "`pty.session.start`",
        "`pty.session.attach`",
        '"code": "string_machine_code"',
        '"message": "human readable summary"',
        '"retryable": false',
        "`conflict_in_flight`",
        "`idempotency_replay`",
        "`upstream_unavailable`",
    ]
    for term in required_terms:
        assert term in text, f"Missing scope/error/mutation baseline term: {term}"


def test_signoff_record_has_approvers_lock_scope_and_revision_rules() -> None:
    text = SIGNOFF_RECORD.read_text(encoding="utf-8")

    required_terms = [
        "Contract pack: `docs/bd-3g1g.2.4-contract-pack-v1.md`",
        "Locked baseline version: `v1.0.0`",
        "Baseline lock date: `2026-02-17` (UTC)",
        "| Phase-1 contract owner | `CoralDog` | `2026-02-17` |",
        "| Contract-pack publisher | `BrightGorge` | `2026-02-17` |",
        "canonical service ownership map and route families",
        "frontend-callable control-plane contract table",
        "reserved `/w/{workspace_id}/...` precedence rules",
        "explicit not-frontend-callable route families",
        "shared error envelope and retry/conflict mutation semantics",
        "scope/capability claim requirements for `workspace-core` + `pty-service`",
        "Later contract changes require an explicit revision issue",
    ]
    for term in required_terms:
        assert term in text, f"Missing sign-off lock term: {term}"
