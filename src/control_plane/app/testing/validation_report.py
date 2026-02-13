"""Generate end-to-end validation reports with go/no-go recommendation.

Bead: bd-223o.16.5 (K5)

Aggregates scenario outcomes, structured run logs, rollout gate status,
and evidence artifacts into a release validation report suitable for
stakeholder review and release gating.

Usage::

    report = ValidationReport.build(
        run_log=run_log,
        evidence_index=evidence_index,
        gate_checklist=gate,
        release_id='v0.1.0',
    )
    print(report.recommendation)   # 'GO', 'NO-GO', or 'CONDITIONAL'
    report.write_markdown(Path('evidence/validation-report.md'))
    report.write_json(Path('evidence/validation-report.json'))
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ResidualRisk:
    """A residual risk identified during validation."""

    category: str  # e.g., 'scenario_failure', 'missing_coverage', 'flaky'
    severity: str  # 'critical', 'high', 'medium', 'low'
    description: str
    scenario_id: str = ''
    mitigation: str = ''


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """End-to-end validation report with release recommendation.

    Attributes:
        release_id: Release identifier being validated.
        recommendation: 'GO', 'NO-GO', or 'CONDITIONAL'.
        summary: High-level summary text.
        scenario_count: Total scenarios executed.
        scenarios_passed: Count of passing scenarios.
        scenarios_failed: Count of failing scenarios.
        total_steps: Total steps across all scenarios.
        steps_passed: Passing steps.
        steps_failed: Failing steps.
        steps_errored: Errored steps.
        artifact_count: Total evidence artifacts collected.
        residual_risks: Identified risks and mitigations.
        failed_scenarios: Details of failed scenarios.
        generated_at: ISO-8601 timestamp of report generation.
        metadata: Additional metadata (base_url, auth mode, etc.).
    """

    release_id: str
    recommendation: str
    summary: str
    scenario_count: int
    scenarios_passed: int
    scenarios_failed: int
    total_steps: int
    steps_passed: int
    steps_failed: int
    steps_errored: int
    artifact_count: int
    residual_risks: tuple[ResidualRisk, ...]
    failed_scenarios: tuple[dict[str, Any], ...]
    generated_at: str
    gate_summary: dict[str, Any] = field(default_factory=dict)
    blocking_gates: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def build(
        *,
        run_log: dict[str, Any],
        evidence_index: dict[str, Any] | None = None,
        gate_checklist: Any | None = None,
        release_id: str = '',
        metadata: dict[str, Any] | None = None,
    ) -> ValidationReport:
        """Build a validation report from a run log and evidence index.

        Args:
            run_log: Output of ``RunLog.to_dict()``.
            evidence_index: Output of ``EvidenceStore.build_index()``.
                If None, artifact count is derived from run_log metadata.
            gate_checklist: Optional ``RolloutGateChecklist`` instance.
                When provided, gate status is incorporated into the
                recommendation and rendered in the report.
            release_id: Release identifier being validated.
            metadata: Additional metadata to include in the report.

        Returns:
            ValidationReport with computed recommendation.
        """
        scenarios = run_log.get('scenarios', [])
        summary_block = run_log.get('summary', {})

        scenario_count = summary_block.get('scenarios', len(scenarios))
        total_steps = summary_block.get('steps', 0)
        steps_pass = summary_block.get('pass', 0)
        steps_fail = summary_block.get('fail', 0)
        steps_error = summary_block.get('error', 0)

        passed_scenarios = [s for s in scenarios if s.get('verdict') == 'pass']
        failed_scenarios_list = [s for s in scenarios if s.get('verdict') != 'pass']

        artifact_count = 0
        if evidence_index:
            artifact_count = evidence_index.get('total_artifacts', 0)

        # Compute residual risks.
        risks = _compute_risks(failed_scenarios_list, scenario_count)

        # Extract gate info.
        gate_summary, blocking_gates_list = _extract_gate_info(
            gate_checklist,
        )

        # Determine recommendation (gate-aware).
        recommendation = _compute_recommendation(
            failed_scenarios_list, risks, scenario_count,
            gate_checklist=gate_checklist,
        )

        # Build summary text.
        summary = _build_summary(
            scenario_count=scenario_count,
            passed=len(passed_scenarios),
            failed=len(failed_scenarios_list),
            total_steps=total_steps,
            steps_pass=steps_pass,
            steps_fail=steps_fail,
            steps_error=steps_error,
            artifact_count=artifact_count,
            recommendation=recommendation,
            gate_checklist=gate_checklist,
        )

        # Use gate's release_id if available.
        effective_release_id = release_id
        if not effective_release_id and gate_checklist is not None:
            effective_release_id = getattr(
                gate_checklist, 'release_id', '',
            )

        return ValidationReport(
            release_id=effective_release_id or 'unspecified',
            recommendation=recommendation,
            summary=summary,
            scenario_count=scenario_count,
            scenarios_passed=len(passed_scenarios),
            scenarios_failed=len(failed_scenarios_list),
            total_steps=total_steps,
            steps_passed=steps_pass,
            steps_failed=steps_fail,
            steps_errored=steps_error,
            artifact_count=artifact_count,
            residual_risks=tuple(risks),
            failed_scenarios=tuple(
                _summarize_failure(s) for s in failed_scenarios_list
            ),
            generated_at=_now_iso(),
            gate_summary=gate_summary,
            blocking_gates=tuple(blocking_gates_list),
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        result: dict[str, Any] = {
            'release_id': self.release_id,
            'recommendation': self.recommendation,
            'summary': self.summary,
            'generated_at': self.generated_at,
            'coverage': {
                'scenarios_total': self.scenario_count,
                'scenarios_passed': self.scenarios_passed,
                'scenarios_failed': self.scenarios_failed,
                'steps_total': self.total_steps,
                'steps_passed': self.steps_passed,
                'steps_failed': self.steps_failed,
                'steps_errored': self.steps_errored,
            },
            'artifacts': self.artifact_count,
            'residual_risks': [
                {
                    'category': r.category,
                    'severity': r.severity,
                    'description': r.description,
                    'scenario_id': r.scenario_id,
                    'mitigation': r.mitigation,
                }
                for r in self.residual_risks
            ],
            'failed_scenarios': list(self.failed_scenarios),
            'metadata': self.metadata,
        }
        if self.gate_summary:
            result['gate_summary'] = self.gate_summary
        if self.blocking_gates:
            result['blocking_gates'] = list(self.blocking_gates)
        return result

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def write_json(self, path: Path) -> None:
        """Write the report as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding='utf-8')

    def to_markdown(self) -> str:
        """Generate a Markdown validation report."""
        lines: list[str] = []

        # Header with verdict.
        icon = '\u2714' if self.recommendation == 'GO' else '\u2718'
        lines.append(
            f'# Validation Report: {self.release_id} '
            f'{icon} {self.recommendation}'
        )
        lines.append('')
        lines.append(f'*Generated: {self.generated_at}*')
        lines.append('')

        # Summary.
        lines.append('## Summary')
        lines.append('')
        lines.append(self.summary)
        lines.append('')

        # Coverage table.
        lines.append('## Coverage')
        lines.append('')
        lines.append('| Metric | Count |')
        lines.append('|--------|-------|')
        lines.append(f'| Scenarios | {self.scenario_count} |')
        lines.append(f'| Passed | {self.scenarios_passed} |')
        lines.append(f'| Failed | {self.scenarios_failed} |')
        lines.append(f'| Total Steps | {self.total_steps} |')
        lines.append(f'| Steps Passed | {self.steps_passed} |')
        lines.append(f'| Steps Failed | {self.steps_failed} |')
        lines.append(f'| Steps Errored | {self.steps_errored} |')
        lines.append(f'| Evidence Artifacts | {self.artifact_count} |')
        lines.append('')

        # Failed scenarios.
        if self.failed_scenarios:
            lines.append('## Failed Scenarios')
            lines.append('')
            for failure in self.failed_scenarios:
                fid = failure.get('scenario_id', '?')
                ftitle = failure.get('title', '')
                lines.append(f'### {fid}: {ftitle}')
                lines.append('')

                failed_steps = failure.get('failed_steps', [])
                for step in failed_steps:
                    lines.append(
                        f'- Step {step.get("step", "?")}: '
                        f'{step.get("method", "")} {step.get("path", "")} '
                        f'\u2192 {step.get("actual_status", "N/A")} '
                        f'(expected {step.get("expected_status", "?")})'
                    )
                    if step.get('error'):
                        lines.append(f'  - {step["error"]}')
                lines.append('')

        # Rollout gate status.
        if self.gate_summary:
            gs = self.gate_summary
            lines.append('## Rollout Gate Status')
            lines.append('')
            lines.append('| Metric | Value |')
            lines.append('|--------|-------|')
            lines.append(f'| Total Items | {gs.get("total", 0)} |')
            lines.append(f'| Required | {gs.get("required", 0)} |')
            lines.append(f'| Passed | {gs.get("passed", 0)} |')
            lines.append(f'| Failed | {gs.get("failed", 0)} |')
            lines.append(f'| Pending | {gs.get("pending", 0)} |')
            blocked = (
                '\u2718 Blocked'
                if gs.get('release_blocked')
                else '\u2714 Clear'
            )
            lines.append(f'| Release Status | {blocked} |')
            lines.append('')

        if self.blocking_gates:
            lines.append('### Blocking Gate Items')
            lines.append('')
            for gate in self.blocking_gates:
                lines.append(
                    f'- [{gate.get("category", "?")}] '
                    f'**{gate.get("key", "?")}**: '
                    f'{gate.get("requirement", "")}'
                )
                if gate.get('detail'):
                    lines.append(f'  - {gate["detail"]}')
            lines.append('')

        # Residual risks.
        if self.residual_risks:
            lines.append('## Residual Risks')
            lines.append('')
            lines.append(
                '| Severity | Category | Description | Mitigation |'
            )
            lines.append(
                '|----------|----------|-------------|------------|'
            )
            for risk in self.residual_risks:
                lines.append(
                    f'| {risk.severity} '
                    f'| {risk.category} '
                    f'| {risk.description} '
                    f'| {risk.mitigation or "None specified"} |'
                )
            lines.append('')

        # Recommendation.
        lines.append('## Recommendation')
        lines.append('')
        lines.append(f'**{self.recommendation}**')
        lines.append('')
        if self.recommendation == 'GO':
            lines.append(
                'All scenarios passed and all required gate items are '
                'satisfied. Release is recommended for deployment.'
            )
        elif self.recommendation == 'CONDITIONAL':
            lines.append(
                'All scenarios passed but some gate items are still '
                'pending. Release may proceed once pending items are '
                'resolved or waived.'
            )
        else:
            lines.append(
                'One or more scenarios failed, gate items are blocking, '
                'or critical risks remain. Release is NOT recommended '
                'until issues are resolved.'
            )
        lines.append('')

        # Footer.
        lines.append('---')
        lines.append(
            '*Generated by boring-ui validation report (K5)*'
        )

        return '\n'.join(lines)

    def write_markdown(self, path: Path) -> None:
        """Write the report as Markdown."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding='utf-8')


# ── Helpers ────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_risks(
    failed_scenarios: list[dict[str, Any]],
    scenario_count: int,
) -> list[ResidualRisk]:
    """Identify residual risks from scenario failures."""
    risks: list[ResidualRisk] = []

    for scenario in failed_scenarios:
        sid = scenario.get('scenario_id', '?')
        title = scenario.get('title', '')
        fail_count = scenario.get('counts', {}).get('fail', 0)
        error_count = scenario.get('counts', {}).get('error', 0)

        if error_count > 0:
            risks.append(ResidualRisk(
                category='scenario_error',
                severity='critical',
                description=(
                    f'{sid} ({title}): {error_count} step(s) '
                    f'returned errors (connectivity/infra)'
                ),
                scenario_id=sid,
                mitigation='Investigate infrastructure and retry',
            ))
        elif fail_count > 0:
            risks.append(ResidualRisk(
                category='scenario_failure',
                severity='high',
                description=(
                    f'{sid} ({title}): {fail_count} step(s) '
                    f'returned unexpected responses'
                ),
                scenario_id=sid,
                mitigation='Fix failing assertions and re-run',
            ))

    # Check coverage.
    if scenario_count == 0:
        risks.append(ResidualRisk(
            category='missing_coverage',
            severity='critical',
            description='No scenarios were executed',
        ))

    return risks


def _compute_recommendation(
    failed_scenarios: list[dict[str, Any]],
    risks: list[ResidualRisk],
    scenario_count: int,
    *,
    gate_checklist: Any | None = None,
) -> str:
    """Determine GO/NO-GO/CONDITIONAL based on failures, risks, and gates."""
    if scenario_count == 0:
        return 'NO-GO'

    # Any critical risk → NO-GO.
    if any(r.severity == 'critical' for r in risks):
        return 'NO-GO'

    # Any scenario failures → NO-GO.
    if failed_scenarios:
        return 'NO-GO'

    # Gate checklist integration.
    if gate_checklist is not None:
        # Any gate failures → NO-GO.
        if getattr(gate_checklist, 'failed_count', 0) > 0:
            return 'NO-GO'

        # Pending required gates → CONDITIONAL.
        blocking_pending = getattr(gate_checklist, 'blocking_pending', ())
        if blocking_pending:
            return 'CONDITIONAL'

    return 'GO'


def _extract_gate_info(
    gate_checklist: Any | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Extract gate summary and blocking items from a checklist.

    Returns (gate_summary_dict, blocking_gates_list).
    """
    if gate_checklist is None:
        return {}, []

    gate_summary = {
        'total': getattr(gate_checklist, 'item_count', 0),
        'required': getattr(gate_checklist, 'required_count', 0),
        'passed': getattr(gate_checklist, 'passed_count', 0),
        'failed': getattr(gate_checklist, 'failed_count', 0),
        'pending': getattr(gate_checklist, 'pending_count', 0),
        'release_blocked': getattr(gate_checklist, 'release_blocked', True),
    }

    blocking = []
    for item in (
        *getattr(gate_checklist, 'blocking_failures', ()),
        *getattr(gate_checklist, 'blocking_pending', ()),
    ):
        blocking.append({
            'category': item.category.value
            if hasattr(item.category, 'value') else str(item.category),
            'key': item.key,
            'requirement': item.requirement,
            'status': item.status.value
            if hasattr(item.status, 'value') else str(item.status),
            'detail': getattr(item, 'detail', ''),
        })

    return gate_summary, blocking


def _build_summary(
    *,
    scenario_count: int,
    passed: int,
    failed: int,
    total_steps: int,
    steps_pass: int,
    steps_fail: int,
    steps_error: int,
    artifact_count: int,
    recommendation: str,
    gate_checklist: Any | None = None,
) -> str:
    """Build a human-readable summary paragraph."""
    if scenario_count == 0:
        return 'No scenarios were executed. Cannot provide recommendation.'

    parts = [
        f'Executed {scenario_count} scenario(s): '
        f'{passed} passed, {failed} failed.',
    ]
    parts.append(
        f'{total_steps} total steps: '
        f'{steps_pass} pass, {steps_fail} fail, {steps_error} error.',
    )
    if artifact_count:
        parts.append(f'{artifact_count} evidence artifact(s) collected.')

    if gate_checklist is not None:
        gate_passed = getattr(gate_checklist, 'passed_count', 0)
        gate_total = getattr(gate_checklist, 'item_count', 0)
        parts.append(f'Gate: {gate_passed}/{gate_total} items satisfied.')

    parts.append(f'Recommendation: **{recommendation}**.')

    return ' '.join(parts)


def _summarize_failure(scenario: dict[str, Any]) -> dict[str, Any]:
    """Extract key failure info from a scenario run log."""
    failed_steps = []
    for step in scenario.get('steps', []):
        if step.get('outcome') in ('fail', 'error'):
            failed_steps.append({
                'step': step.get('step'),
                'method': step.get('method'),
                'path': step.get('path'),
                'expected_status': step.get('expected', {}).get('status'),
                'actual_status': step.get('observed', {}).get('status'),
                'error': step.get('error_detail'),
            })

    return {
        'scenario_id': scenario.get('scenario_id', '?'),
        'title': scenario.get('title', ''),
        'verdict': scenario.get('verdict', 'unknown'),
        'failed_steps': failed_steps,
    }
