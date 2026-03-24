"""Workflow Compliance checks (Phase W).

Grades whether the agent used supported platform workflows independently
from whether the resulting app eventually worked. Based on the observed
command log from the runner.
"""

from __future__ import annotations

import re
from typing import Any

from tests.eval.check_catalog import CATALOG
from tests.eval.contracts import CheckResult, ObservedCommand, RunManifest
from tests.eval.reason_codes import Attribution, CheckStatus


# ---------------------------------------------------------------------------
# Check context
# ---------------------------------------------------------------------------

class WorkflowContext:
    """Shared state for workflow checks."""

    def __init__(
        self,
        manifest: RunManifest,
        command_log: list[ObservedCommand],
        agent_text: str = "",
    ) -> None:
        self.manifest = manifest
        self.commands = command_log
        self.agent_text = agent_text
        # Pre-compute normalized command strings
        self._cmd_strings = [c.command.strip() for c in command_log]


def run_workflow_checks(
    manifest: RunManifest,
    command_log: list[ObservedCommand],
    agent_text: str = "",
) -> list[CheckResult]:
    """Run all 5 workflow compliance checks."""
    ctx = WorkflowContext(manifest, command_log, agent_text)
    return [
        _check_scaffold_supported(ctx),
        _check_doctor_supported(ctx),
        _check_neon_supported(ctx),
        _check_deploy_supported(ctx),
        _check_no_unsupported_bypass(ctx),
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


def _has_command(ctx: WorkflowContext, pattern: str) -> ObservedCommand | None:
    """Find the first command matching a regex pattern."""
    for i, cmd_str in enumerate(ctx._cmd_strings):
        if re.search(pattern, cmd_str, re.IGNORECASE):
            return ctx.commands[i]
    # Fallback: check agent text for command patterns
    return None


def _text_has_pattern(ctx: WorkflowContext, pattern: str) -> bool:
    """Check if the agent text contains a command pattern."""
    return bool(re.search(pattern, ctx.agent_text, re.IGNORECASE))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _check_scaffold_supported(ctx: WorkflowContext) -> CheckResult:
    cid = "workflow.scaffold_supported"
    cmd = _has_command(ctx, r"bui\s+init\b")
    if cmd:
        return _pass(cid, f"bui init found: {cmd.command[:60]}")

    # Fallback: check agent text
    if _text_has_pattern(ctx, r"bui\s+init\b"):
        return _pass(cid, "bui init found in agent output (lower trust)")

    return _fail(
        cid, "WORKFLOW_BUI_NOT_USED",
        "No bui init command found in command log or agent output",
    )


def _check_doctor_supported(ctx: WorkflowContext) -> CheckResult:
    cid = "workflow.doctor_supported"
    cmd = _has_command(ctx, r"bui\s+doctor\b")
    if cmd:
        detail = f"bui doctor found (exit={cmd.exit_code})"
        return _pass(cid, detail)

    if _text_has_pattern(ctx, r"bui\s+doctor\b"):
        return _pass(cid, "bui doctor found in agent output (lower trust)")

    return _fail(
        cid, "WORKFLOW_DOCTOR_SKIPPED",
        "No bui doctor command found",
    )


def _check_neon_supported(ctx: WorkflowContext) -> CheckResult:
    cid = "workflow.neon_supported"
    cmd = _has_command(ctx, r"bui\s+neon\s+setup\b")
    if cmd:
        return _pass(cid, f"bui neon setup found: {cmd.command[:60]}")

    if _text_has_pattern(ctx, r"bui\s+neon\s+setup\b"):
        return _pass(cid, "bui neon setup found in agent output (lower trust)")

    return _fail(
        cid, "WORKFLOW_NEON_SETUP_SKIPPED",
        "No bui neon setup command found",
    )


def _check_deploy_supported(ctx: WorkflowContext) -> CheckResult:
    cid = "workflow.deploy_supported"
    cmd = _has_command(ctx, r"bui\s+deploy\b")
    if cmd:
        return _pass(cid, f"bui deploy found (exit={cmd.exit_code})")

    if _text_has_pattern(ctx, r"bui\s+deploy\b"):
        return _pass(cid, "bui deploy found in agent output (lower trust)")

    return _fail(
        cid, "WORKFLOW_DEPLOY_CMD_SKIPPED",
        "No bui deploy command found",
    )


def _check_no_unsupported_bypass(ctx: WorkflowContext) -> CheckResult:
    """Check that core steps weren't bypassed with manual commands."""
    cid = "workflow.no_unsupported_bypass"

    # Patterns that indicate manual bypasses of bui workflows
    bypass_patterns = [
        (r"fly\s+deploy\b", "fly deploy (should use bui deploy)"),
        (r"flyctl\s+deploy\b", "flyctl deploy (should use bui deploy)"),
        (r"fly\s+apps\s+create\b", "fly apps create (should use bui init)"),
        (r"neon\s+projects?\s+create\b", "neon project create (should use bui neon setup)"),
    ]

    bypasses: list[str] = []
    for pattern, desc in bypass_patterns:
        cmd = _has_command(ctx, pattern)
        if cmd:
            bypasses.append(f"{desc}: {cmd.command[:40]}")

    if bypasses:
        return _fail(
            cid, "WORKFLOW_BYPASS_DETECTED",
            f"Manual bypasses: {'; '.join(bypasses)}",
        )

    return _pass(cid, "No unsupported bypasses detected")
