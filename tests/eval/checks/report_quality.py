"""Report Quality & Agent Behavior checks (Phase E).

Grades whether the agent's final report is present, parseable, complete,
and truthful relative to harness-observed evidence.
"""

from __future__ import annotations

from typing import Any

from tests.eval.check_catalog import CATALOG
from tests.eval.contracts import CheckResult, ObservedCommand, RunManifest
from tests.eval.parsing import extract_bui_commands, extract_report_json
from tests.eval.reason_codes import Attribution, CheckStatus
from tests.eval.report_schema import (
    BEGIN_MARKER,
    END_MARKER,
    validate_report,
)


# ---------------------------------------------------------------------------
# Check context
# ---------------------------------------------------------------------------

class ReportQualityContext:
    """Shared state for report quality checks."""

    def __init__(
        self,
        manifest: RunManifest,
        agent_text: str,
        command_log: list[ObservedCommand] | None = None,
        harness_observations: dict[str, Any] | None = None,
    ) -> None:
        self.manifest = manifest
        self.agent_text = agent_text
        self.command_log = command_log or []
        self.observations = harness_observations or {}
        self.report: dict[str, Any] | None = extract_report_json(agent_text)


def run_report_quality_checks(
    manifest: RunManifest,
    agent_text: str,
    command_log: list[ObservedCommand] | None = None,
    harness_observations: dict[str, Any] | None = None,
) -> list[CheckResult]:
    """Run all 11 report quality checks."""
    ctx = ReportQualityContext(manifest, agent_text, command_log, harness_observations)
    return [
        _check_human_summary_present(ctx),
        _check_machine_json_present(ctx),
        _check_json_parseable(ctx),
        _check_includes_identifiers(ctx),
        _check_includes_commands_run(ctx),
        _check_includes_local_results(ctx),
        _check_includes_live_results(ctx),
        _check_includes_known_issues(ctx),
        _check_claims_match_evidence(ctx),
        _check_commands_match_observed(ctx),
        _check_scope_statement_truthful(ctx),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _spec(check_id: str) -> dict[str, Any]:
    s = CATALOG[check_id]
    return {"id": check_id, "category": s.category, "weight": s.weight}


def _pass(check_id: str, detail: str = "") -> CheckResult:
    return CheckResult(**_spec(check_id), status=CheckStatus.PASS, detail=detail)


def _fail(check_id: str, reason_code: str, detail: str = "") -> CheckResult:
    return CheckResult(
        **_spec(check_id),
        status=CheckStatus.FAIL,
        reason_code=reason_code,
        attribution=Attribution.AGENT,
        detail=detail,
    )


def _skip(check_id: str, detail: str, blocked_by: list[str] | None = None) -> CheckResult:
    return CheckResult(
        **_spec(check_id),
        status=CheckStatus.SKIP,
        detail=detail,
        skipped=True,
        blocked_by=blocked_by or [],
    )


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_human_summary_present(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.human_summary_present"
    # Human summary should be outside the JSON markers
    text = ctx.agent_text
    if BEGIN_MARKER in text:
        before_marker = text[:text.index(BEGIN_MARKER)]
    else:
        before_marker = text

    # Heuristic: at least 50 chars of text that looks like a summary
    stripped = before_marker.strip()
    if len(stripped) >= 50:
        return _pass(cid, f"Summary found ({len(stripped)} chars before JSON)")

    # Also check after the marker
    if END_MARKER in text:
        after_marker = text[text.index(END_MARKER) + len(END_MARKER):]
        if len(after_marker.strip()) >= 50:
            return _pass(cid, f"Summary found ({len(after_marker.strip())} chars after JSON)")

    if len(stripped) > 0:
        return _pass(cid, f"Brief summary found ({len(stripped)} chars)")

    return _fail(cid, "REPORT_FIELD_MISSING", "No human-readable summary found")


def _check_machine_json_present(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.machine_json_present"
    if BEGIN_MARKER in ctx.agent_text and END_MARKER in ctx.agent_text:
        return _pass(cid, "BEGIN/END markers found")
    if ctx.report is not None:
        return _pass(cid, "JSON report extracted (markers missing — reduced credit)")
    return _fail(cid, "REPORT_JSON_MISSING", "No machine-readable JSON block found")


def _check_json_parseable(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.json_parseable"
    if ctx.report is None:
        return _skip(cid, "No report to parse", blocked_by=["report.machine_json_present"])
    ok, errors = validate_report(ctx.report)
    if ok:
        return _pass(cid, "Report validates against schema")
    return _fail(cid, "REPORT_JSON_INVALID", f"Validation errors: {'; '.join(errors[:3])}")


def _check_includes_identifiers(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.includes_identifiers"
    if ctx.report is None:
        return _skip(cid, "No report", blocked_by=["report.json_parseable"])

    required = ["app_slug", "project_root"]
    missing = [f for f in required if not ctx.report.get(f)]
    if missing:
        return _fail(cid, "REPORT_FIELD_MISSING", f"Missing: {', '.join(missing)}")
    return _pass(cid, "All identifiers present")


def _check_includes_commands_run(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.includes_commands_run"
    if ctx.report is None:
        return _skip(cid, "No report", blocked_by=["report.json_parseable"])

    cmds = ctx.report.get("commands_run", [])
    if isinstance(cmds, list) and len(cmds) > 0:
        return _pass(cid, f"{len(cmds)} commands listed")
    return _fail(cid, "REPORT_FIELD_MISSING", "commands_run is empty or missing")


def _check_includes_local_results(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.includes_local_results"
    if ctx.report is None:
        return _skip(cid, "No report", blocked_by=["report.json_parseable"])

    checks = ctx.report.get("local_checks", [])
    if isinstance(checks, list) and len(checks) > 0:
        return _pass(cid, f"{len(checks)} local checks listed")
    return _fail(cid, "REPORT_FIELD_MISSING", "local_checks is empty or missing")


def _check_includes_live_results(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.includes_live_results"
    if ctx.report is None:
        return _skip(cid, "No report", blocked_by=["report.json_parseable"])

    checks = ctx.report.get("live_checks", [])
    if isinstance(checks, list) and len(checks) > 0:
        return _pass(cid, f"{len(checks)} live checks listed")
    return _fail(cid, "REPORT_FIELD_MISSING", "live_checks is empty or missing")


def _check_includes_known_issues(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.includes_known_issues"
    if ctx.report is None:
        return _skip(cid, "No report", blocked_by=["report.json_parseable"])

    issues = ctx.report.get("known_issues")
    if issues is not None:  # Empty list is fine — it means "no issues"
        return _pass(cid, f"{len(issues)} known issues listed")
    return _fail(cid, "REPORT_FIELD_MISSING", "known_issues field missing")


def _check_claims_match_evidence(ctx: ReportQualityContext) -> CheckResult:
    """must_pass: Claims consistent with harness-observed evidence."""
    cid = "report.claims_match_evidence"
    if ctx.report is None:
        return _skip(cid, "No report", blocked_by=["report.json_parseable"])

    discrepancies: list[str] = []

    # Check eval_id matches
    report_eval_id = ctx.report.get("eval_id", "")
    if report_eval_id and report_eval_id != ctx.manifest.eval_id:
        discrepancies.append(
            f"eval_id mismatch: report={report_eval_id!r} vs manifest={ctx.manifest.eval_id!r}"
        )

    # Check nonce matches
    report_nonce = ctx.report.get("verification_nonce", "")
    if report_nonce and report_nonce != ctx.manifest.verification_nonce:
        discrepancies.append(
            f"nonce mismatch: report={report_nonce!r} vs manifest={ctx.manifest.verification_nonce!r}"
        )

    # Check step claims vs harness observations
    steps = ctx.report.get("steps", {})
    for step_name, step_data in steps.items():
        if not isinstance(step_data, dict):
            continue
        claimed_status = step_data.get("status", "")
        if claimed_status == "succeeded":
            # Cross-reference with harness observations if available
            obs_key = f"step_{step_name}_succeeded"
            if ctx.observations.get(obs_key) is False:
                discrepancies.append(
                    f"Agent claims {step_name} succeeded but harness observed failure"
                )

    if discrepancies:
        return _fail(
            cid, "REPORT_CLAIM_DISPROVED",
            f"{len(discrepancies)} discrepancies: {'; '.join(discrepancies[:2])}",
        )
    return _pass(cid, "Claims consistent with evidence")


def _check_commands_match_observed(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.commands_match_observed"
    if ctx.report is None:
        return _skip(cid, "No report", blocked_by=["report.json_parseable"])

    reported_cmds = ctx.report.get("commands_run", [])
    if not isinstance(reported_cmds, list) or not reported_cmds:
        return _fail(cid, "REPORT_FIELD_MISSING", "No commands_run in report")

    if not ctx.command_log:
        # Can't cross-reference without command log
        return _pass(cid, "No command log to cross-reference (advisory)")

    # Check that reported bui commands appear in command log
    observed_strs = {c.command.strip() for c in ctx.command_log}
    mismatches: list[str] = []
    for reported in reported_cmds:
        # Fuzzy match: reported command should be a substring of some observed command
        found = any(reported in obs or obs in reported for obs in observed_strs)
        if not found:
            mismatches.append(reported)

    if len(mismatches) > len(reported_cmds) / 2:
        return _fail(
            cid, "REPORT_INCONSISTENT",
            f"{len(mismatches)}/{len(reported_cmds)} reported commands not in observed log",
        )

    return _pass(cid, f"{len(reported_cmds)} commands, {len(mismatches)} unmatched (acceptable)")


def _check_scope_statement_truthful(ctx: ReportQualityContext) -> CheckResult:
    cid = "report.scope_statement_truthful"
    if ctx.report is None:
        return _skip(cid, "No report", blocked_by=["report.json_parseable"])

    # Check for scope claims in the report
    # This is a lightweight check — deeper scope verification is in security checks
    app_slug = ctx.report.get("app_slug", "")
    if app_slug and app_slug != ctx.manifest.app_slug:
        return _fail(
            cid, "REPORT_INCONSISTENT",
            f"app_slug mismatch: {app_slug!r} vs {ctx.manifest.app_slug!r}",
        )

    return _pass(cid, "Scope identifiers are consistent")
