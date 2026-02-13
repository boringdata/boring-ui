"""Tests for end-to-end validation report generation.

Bead: bd-223o.16.5 (K5)

Tests cover:
  - ValidationReport.build with all-passing scenarios
  - ValidationReport.build with failures → NO-GO
  - ValidationReport.build with errors → NO-GO (critical risk)
  - ValidationReport.build with no scenarios → NO-GO
  - ValidationReport.build with evidence index artifacts
  - ValidationReport to_dict and to_json serialization
  - ValidationReport to_markdown output structure
  - ValidationReport write_json and write_markdown file creation
  - ResidualRisk computation from failures and errors
  - Recommendation logic (GO/NO-GO/CONDITIONAL rules)
  - Gate checklist integration (J6 rollout gate)
  - Summary text generation
  - Failed scenario detail extraction
  - Integration with RunLog.to_dict() format
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from control_plane.app.operations.rollout_gate import (
    GateCategory,
    GateItem,
    GateStatus,
    RolloutGateChecklist,
    build_rollout_gate_checklist,
)
from control_plane.app.testing.validation_report import (
    ResidualRisk,
    ValidationReport,
    _build_summary,
    _compute_recommendation,
    _compute_risks,
    _extract_gate_info,
    _summarize_failure,
)


# ── Test data builders ────────────────────────────────────────────


def _make_run_log(
    *,
    scenarios: list[dict] | None = None,
    overall_passed: bool = True,
) -> dict:
    """Build a run_log dict matching RunLog.to_dict() output."""
    if scenarios is None:
        scenarios = [
            _make_scenario_log('S-001', 'Login', verdict='pass'),
            _make_scenario_log('S-002', 'Workspace', verdict='pass'),
        ]

    total = sum(s['counts']['total'] for s in scenarios)
    passed = sum(s['counts']['pass'] for s in scenarios)
    failed = sum(s['counts']['fail'] for s in scenarios)
    errored = sum(s['counts']['error'] for s in scenarios)

    return {
        'run_id': 'run-test123',
        'created_at': '2026-02-13T12:00:00+00:00',
        'overall_passed': overall_passed,
        'summary': {
            'scenarios': len(scenarios),
            'steps': total,
            'pass': passed,
            'fail': failed,
            'error': errored,
        },
        'metadata': {'base_url': 'http://localhost:8000'},
        'scenarios': scenarios,
    }


def _make_scenario_log(
    scenario_id: str = 'S-001',
    title: str = 'Test Scenario',
    *,
    verdict: str = 'pass',
    steps: list[dict] | None = None,
) -> dict:
    if steps is None:
        if verdict == 'pass':
            steps = [
                _make_step_log(1, outcome='pass'),
                _make_step_log(2, outcome='pass'),
            ]
        else:
            steps = [
                _make_step_log(1, outcome='pass'),
                _make_step_log(
                    2, outcome='fail',
                    actual_status=500,
                    error_detail='Expected 200, got 500',
                ),
            ]

    counts = {
        'total': len(steps),
        'pass': sum(1 for s in steps if s['outcome'] == 'pass'),
        'fail': sum(1 for s in steps if s['outcome'] == 'fail'),
        'error': sum(1 for s in steps if s['outcome'] == 'error'),
        'skip': sum(1 for s in steps if s['outcome'] == 'skip'),
    }

    return {
        'scenario_id': scenario_id,
        'title': title,
        'started_at': '2026-02-13T12:00:00+00:00',
        'finished_at': '2026-02-13T12:00:01+00:00',
        'duration_ms': 1000.0,
        'verdict': verdict,
        'counts': counts,
        'steps': steps,
    }


def _make_step_log(
    step_number: int = 1,
    *,
    method: str = 'GET',
    path: str = '/api/v1/me',
    outcome: str = 'pass',
    expected_status: int = 200,
    actual_status: int = 200,
    error_detail: str | None = None,
) -> dict:
    result = {
        'step': step_number,
        'method': method,
        'path': path,
        'outcome': outcome,
        'timestamp': '2026-02-13T12:00:00+00:00',
        'duration_ms': 42.5,
        'request_id': f'req-{step_number:03d}',
        'expected': {'status': expected_status},
        'observed': {'status': actual_status},
    }
    if error_detail:
        result['error_detail'] = error_detail
    return result


def _make_evidence_index(
    *,
    scenario_count: int = 2,
    total_artifacts: int = 5,
    overall_passed: bool = True,
) -> dict:
    return {
        'generated_at': '2026-02-13T12:00:00+00:00',
        'scenario_count': scenario_count,
        'overall_passed': overall_passed,
        'total_artifacts': total_artifacts,
        'total_steps_pass': 4,
        'total_steps_fail': 0,
        'total_steps_error': 0,
        'scenarios': [],
    }


# ── ValidationReport.build ────────────────────────────────────────


class TestBuildAllPass:
    def test_go_recommendation(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        assert report.recommendation == 'GO'

    def test_scenario_counts(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        assert report.scenario_count == 2
        assert report.scenarios_passed == 2
        assert report.scenarios_failed == 0

    def test_step_counts(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        assert report.total_steps == 4
        assert report.steps_passed == 4
        assert report.steps_failed == 0
        assert report.steps_errored == 0

    def test_no_residual_risks(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        assert len(report.residual_risks) == 0

    def test_no_failed_scenarios(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        assert len(report.failed_scenarios) == 0


class TestBuildWithFailures:
    def test_nogo_on_failure(self):
        run_log = _make_run_log(
            scenarios=[
                _make_scenario_log('S-001', 'Login', verdict='pass'),
                _make_scenario_log('S-002', 'Workspace', verdict='fail'),
            ],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        assert report.recommendation == 'NO-GO'

    def test_failed_scenario_detail(self):
        run_log = _make_run_log(
            scenarios=[
                _make_scenario_log('S-002', 'Workspace', verdict='fail'),
            ],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        assert report.scenarios_failed == 1
        assert len(report.failed_scenarios) == 1
        assert report.failed_scenarios[0]['scenario_id'] == 'S-002'

    def test_residual_risk_for_failure(self):
        run_log = _make_run_log(
            scenarios=[
                _make_scenario_log('S-002', 'Workspace', verdict='fail'),
            ],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        assert len(report.residual_risks) == 1
        risk = report.residual_risks[0]
        assert risk.severity == 'high'
        assert risk.category == 'scenario_failure'
        assert 'S-002' in risk.description


class TestBuildWithErrors:
    def test_nogo_on_errors(self):
        error_step = _make_step_log(
            1, outcome='error', actual_status=0,
            error_detail='ConnectError: refused',
        )
        run_log = _make_run_log(
            scenarios=[
                _make_scenario_log(
                    'S-001', 'Login', verdict='fail',
                    steps=[error_step],
                ),
            ],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        assert report.recommendation == 'NO-GO'

    def test_critical_risk_for_errors(self):
        error_step = _make_step_log(
            1, outcome='error', error_detail='ConnectError',
        )
        run_log = _make_run_log(
            scenarios=[
                _make_scenario_log(
                    'S-001', 'Login', verdict='fail',
                    steps=[error_step],
                ),
            ],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        assert any(r.severity == 'critical' for r in report.residual_risks)


class TestBuildNoScenarios:
    def test_nogo_with_no_scenarios(self):
        run_log = _make_run_log(scenarios=[])
        report = ValidationReport.build(run_log=run_log)
        assert report.recommendation == 'NO-GO'

    def test_critical_risk_no_coverage(self):
        run_log = _make_run_log(scenarios=[])
        report = ValidationReport.build(run_log=run_log)
        assert any(
            r.category == 'missing_coverage'
            for r in report.residual_risks
        )


class TestBuildWithEvidence:
    def test_artifact_count_from_index(self):
        run_log = _make_run_log()
        index = _make_evidence_index(total_artifacts=12)
        report = ValidationReport.build(
            run_log=run_log, evidence_index=index,
        )
        assert report.artifact_count == 12

    def test_no_evidence_index(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        assert report.artifact_count == 0


class TestBuildMetadata:
    def test_release_id(self):
        run_log = _make_run_log()
        report = ValidationReport.build(
            run_log=run_log, release_id='v0.1.0',
        )
        assert report.release_id == 'v0.1.0'

    def test_default_release_id(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        assert report.release_id == 'unspecified'

    def test_metadata_included(self):
        run_log = _make_run_log()
        report = ValidationReport.build(
            run_log=run_log,
            metadata={'env': 'staging', 'auth_mode': 'cookie'},
        )
        assert report.metadata['env'] == 'staging'


# ── Serialization ─────────────────────────────────────────────────


class TestSerialization:
    def test_to_dict(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        d = report.to_dict()

        assert d['recommendation'] == 'GO'
        assert d['coverage']['scenarios_total'] == 2
        assert d['coverage']['steps_total'] == 4
        assert 'generated_at' in d

    def test_to_json_valid(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        parsed = json.loads(report.to_json())
        assert parsed['recommendation'] == 'GO'

    def test_to_json_round_trip(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        parsed = json.loads(report.to_json())
        assert parsed == report.to_dict()

    def test_write_json(self, tmp_path: Path):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        out = tmp_path / 'sub' / 'report.json'
        report.write_json(out)
        assert out.exists()
        parsed = json.loads(out.read_text())
        assert parsed['recommendation'] == 'GO'

    def test_failed_scenarios_in_dict(self):
        run_log = _make_run_log(
            scenarios=[_make_scenario_log('S-001', verdict='fail')],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        d = report.to_dict()
        assert len(d['failed_scenarios']) == 1
        assert d['failed_scenarios'][0]['scenario_id'] == 'S-001'

    def test_risks_in_dict(self):
        run_log = _make_run_log(
            scenarios=[_make_scenario_log('S-001', verdict='fail')],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        d = report.to_dict()
        assert len(d['residual_risks']) > 0
        assert 'severity' in d['residual_risks'][0]


# ── Markdown ──────────────────────────────────────────────────────


class TestMarkdown:
    def test_go_header(self):
        run_log = _make_run_log()
        report = ValidationReport.build(
            run_log=run_log, release_id='v0.1.0',
        )
        md = report.to_markdown()
        assert '# Validation Report: v0.1.0 \u2714 GO' in md

    def test_nogo_header(self):
        run_log = _make_run_log(
            scenarios=[_make_scenario_log(verdict='fail')],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        md = report.to_markdown()
        assert '\u2718 NO-GO' in md

    def test_coverage_table(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        md = report.to_markdown()
        assert '| Scenarios | 2 |' in md
        assert '| Total Steps | 4 |' in md

    def test_failed_scenarios_section(self):
        run_log = _make_run_log(
            scenarios=[
                _make_scenario_log('S-002', 'Workspace', verdict='fail'),
            ],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        md = report.to_markdown()
        assert '## Failed Scenarios' in md
        assert 'S-002: Workspace' in md

    def test_no_failed_section_when_all_pass(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        md = report.to_markdown()
        assert '## Failed Scenarios' not in md

    def test_residual_risks_table(self):
        run_log = _make_run_log(
            scenarios=[_make_scenario_log(verdict='fail')],
            overall_passed=False,
        )
        report = ValidationReport.build(run_log=run_log)
        md = report.to_markdown()
        assert '## Residual Risks' in md
        assert '| high |' in md

    def test_recommendation_section(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        md = report.to_markdown()
        assert '## Recommendation' in md
        assert '**GO**' in md
        assert 'recommended for deployment' in md

    def test_footer(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        md = report.to_markdown()
        assert 'boring-ui validation report (K5)' in md

    def test_write_markdown(self, tmp_path: Path):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        out = tmp_path / 'sub' / 'report.md'
        report.write_markdown(out)
        assert out.exists()
        content = out.read_text()
        assert '# Validation Report' in content

    def test_artifacts_in_coverage(self):
        run_log = _make_run_log()
        index = _make_evidence_index(total_artifacts=8)
        report = ValidationReport.build(
            run_log=run_log, evidence_index=index,
        )
        md = report.to_markdown()
        assert '| Evidence Artifacts | 8 |' in md


# ── Helper functions ──────────────────────────────────────────────


class TestComputeRisks:
    def test_no_risks_on_success(self):
        risks = _compute_risks([], scenario_count=2)
        assert risks == []

    def test_failure_risk(self):
        failed = [_make_scenario_log('S-001', verdict='fail')]
        risks = _compute_risks(failed, scenario_count=2)
        assert len(risks) == 1
        assert risks[0].severity == 'high'

    def test_error_risk_is_critical(self):
        error_step = _make_step_log(1, outcome='error')
        failed = [
            _make_scenario_log(
                'S-001', verdict='fail', steps=[error_step],
            ),
        ]
        risks = _compute_risks(failed, scenario_count=1)
        assert any(r.severity == 'critical' for r in risks)

    def test_no_scenarios_risk(self):
        risks = _compute_risks([], scenario_count=0)
        assert len(risks) == 1
        assert risks[0].category == 'missing_coverage'


class TestComputeRecommendation:
    def test_go_when_all_pass(self):
        assert _compute_recommendation([], [], 2) == 'GO'

    def test_nogo_on_failure(self):
        failed = [{'scenario_id': 'S-001'}]
        assert _compute_recommendation(failed, [], 2) == 'NO-GO'

    def test_nogo_on_critical_risk(self):
        risks = [ResidualRisk(
            category='test', severity='critical', description='test',
        )]
        assert _compute_recommendation([], risks, 2) == 'NO-GO'

    def test_nogo_on_zero_scenarios(self):
        assert _compute_recommendation([], [], 0) == 'NO-GO'


class TestBuildSummary:
    def test_passing_summary(self):
        summary = _build_summary(
            scenario_count=3, passed=3, failed=0,
            total_steps=9, steps_pass=9, steps_fail=0, steps_error=0,
            artifact_count=15, recommendation='GO',
        )
        assert '3 scenario(s)' in summary
        assert '9 total steps' in summary
        assert '15 evidence artifact(s)' in summary
        assert '**GO**' in summary

    def test_no_scenarios_summary(self):
        summary = _build_summary(
            scenario_count=0, passed=0, failed=0,
            total_steps=0, steps_pass=0, steps_fail=0, steps_error=0,
            artifact_count=0, recommendation='NO-GO',
        )
        assert 'No scenarios' in summary

    def test_no_artifacts_in_summary(self):
        summary = _build_summary(
            scenario_count=1, passed=1, failed=0,
            total_steps=2, steps_pass=2, steps_fail=0, steps_error=0,
            artifact_count=0, recommendation='GO',
        )
        assert 'artifact' not in summary


class TestSummarizeFailure:
    def test_extracts_failed_steps(self):
        step = _make_step_log(
            2, outcome='fail', actual_status=500,
            error_detail='Server error',
        )
        scenario = _make_scenario_log(
            'S-002', 'Workspace', verdict='fail', steps=[
                _make_step_log(1, outcome='pass'),
                step,
            ],
        )
        result = _summarize_failure(scenario)
        assert result['scenario_id'] == 'S-002'
        assert len(result['failed_steps']) == 1
        assert result['failed_steps'][0]['error'] == 'Server error'

    def test_no_failed_steps_on_pass(self):
        scenario = _make_scenario_log('S-001', verdict='pass')
        result = _summarize_failure(scenario)
        assert result['failed_steps'] == []


# ── ResidualRisk ──────────────────────────────────────────────────


class TestResidualRisk:
    def test_creation(self):
        risk = ResidualRisk(
            category='scenario_failure',
            severity='high',
            description='Login failed',
            scenario_id='S-001',
            mitigation='Fix auth flow',
        )
        assert risk.category == 'scenario_failure'
        assert risk.mitigation == 'Fix auth flow'

    def test_frozen(self):
        risk = ResidualRisk(
            category='test', severity='low', description='test',
        )
        with pytest.raises(AttributeError):
            risk.severity = 'critical'  # type: ignore[misc]

    def test_defaults(self):
        risk = ResidualRisk(
            category='test', severity='low', description='test',
        )
        assert risk.scenario_id == ''
        assert risk.mitigation == ''


# ── Gate checklist helpers ───────────────────────────────────────


def _make_gate(
    *,
    all_passed: bool = False,
    all_pending: bool = True,
    has_failures: bool = False,
    release_id: str = 'v0.1.0',
    owner: str = 'release_manager',
) -> RolloutGateChecklist:
    """Build a gate checklist for testing.

    Default: all items PENDING (release blocked).
    all_passed=True: all items PASSED (release clear).
    has_failures=True: first required item FAILED.
    """
    gate = build_rollout_gate_checklist(
        release_id=release_id, owner=owner,
    )
    if all_passed:
        items = tuple(
            GateItem(
                category=item.category,
                key=item.key,
                requirement=item.requirement,
                evidence_source=item.evidence_source,
                required=item.required,
                status=GateStatus.PASSED,
            )
            for item in gate.items
        )
        return RolloutGateChecklist(
            items=items, release_id=release_id, owner=owner,
        )
    if has_failures:
        items_list = list(gate.items)
        first = items_list[0]
        items_list[0] = GateItem(
            category=first.category,
            key=first.key,
            requirement=first.requirement,
            evidence_source=first.evidence_source,
            required=first.required,
            status=GateStatus.FAILED,
            detail='SLO alerts not defined',
        )
        # Set rest to passed.
        for i in range(1, len(items_list)):
            item = items_list[i]
            items_list[i] = GateItem(
                category=item.category,
                key=item.key,
                requirement=item.requirement,
                evidence_source=item.evidence_source,
                required=item.required,
                status=GateStatus.PASSED,
            )
        return RolloutGateChecklist(
            items=tuple(items_list),
            release_id=release_id,
            owner=owner,
        )
    return gate


# =====================================================================
# Gate integration — recommendation logic with gate checklist
# =====================================================================


class TestGateIntegrationRecommendation:

    def test_go_with_all_gates_passed(self):
        run_log = _make_run_log()
        gate = _make_gate(all_passed=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert report.recommendation == 'GO'

    def test_nogo_with_gate_failure(self):
        run_log = _make_run_log()
        gate = _make_gate(has_failures=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert report.recommendation == 'NO-GO'

    def test_conditional_with_pending_gates(self):
        run_log = _make_run_log()
        gate = _make_gate(all_pending=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert report.recommendation == 'CONDITIONAL'

    def test_nogo_overrides_conditional_on_scenario_failure(self):
        run_log = _make_run_log(
            scenarios=[_make_scenario_log(verdict='fail')],
            overall_passed=False,
        )
        gate = _make_gate(all_pending=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert report.recommendation == 'NO-GO'

    def test_no_gate_defaults_to_scenario_only(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        assert report.recommendation == 'GO'


# =====================================================================
# Gate integration — gate summary in report
# =====================================================================


class TestGateSummaryInReport:

    def test_gate_summary_present_when_gate_provided(self):
        run_log = _make_run_log()
        gate = _make_gate(all_passed=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert report.gate_summary
        assert report.gate_summary['total'] == gate.item_count
        assert report.gate_summary['passed'] == gate.passed_count

    def test_gate_summary_empty_when_no_gate(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        assert report.gate_summary == {}

    def test_blocking_gates_populated_on_failure(self):
        run_log = _make_run_log()
        gate = _make_gate(has_failures=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert len(report.blocking_gates) >= 1
        assert report.blocking_gates[0]['key'] == 'slo_alerts_defined'
        assert report.blocking_gates[0]['status'] == 'failed'

    def test_blocking_gates_populated_on_pending(self):
        run_log = _make_run_log()
        gate = _make_gate(all_pending=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert len(report.blocking_gates) > 0
        assert report.blocking_gates[0]['status'] == 'pending'

    def test_no_blocking_gates_when_all_passed(self):
        run_log = _make_run_log()
        gate = _make_gate(all_passed=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert len(report.blocking_gates) == 0

    def test_release_id_from_gate(self):
        run_log = _make_run_log()
        gate = _make_gate(all_passed=True, release_id='v1.2.3')
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert report.release_id == 'v1.2.3'

    def test_explicit_release_id_overrides_gate(self):
        run_log = _make_run_log()
        gate = _make_gate(all_passed=True, release_id='v1.2.3')
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
            release_id='v2.0.0',
        )
        assert report.release_id == 'v2.0.0'


# =====================================================================
# Gate integration — serialization
# =====================================================================


class TestGateSerialization:

    def test_gate_in_to_dict(self):
        run_log = _make_run_log()
        gate = _make_gate(all_passed=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        d = report.to_dict()
        assert 'gate_summary' in d
        assert d['gate_summary']['total'] == gate.item_count

    def test_blocking_gates_in_to_dict(self):
        run_log = _make_run_log()
        gate = _make_gate(has_failures=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        d = report.to_dict()
        assert 'blocking_gates' in d
        assert len(d['blocking_gates']) >= 1

    def test_no_gate_keys_when_no_gate(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        d = report.to_dict()
        assert 'gate_summary' not in d
        assert 'blocking_gates' not in d

    def test_gate_json_round_trip(self):
        import json
        run_log = _make_run_log()
        gate = _make_gate(has_failures=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        parsed = json.loads(report.to_json())
        assert parsed['gate_summary']['failed'] > 0
        assert len(parsed['blocking_gates']) >= 1


# =====================================================================
# Gate integration — markdown output
# =====================================================================


class TestGateMarkdown:

    def test_gate_section_in_markdown(self):
        run_log = _make_run_log()
        gate = _make_gate(all_passed=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        md = report.to_markdown()
        assert '## Rollout Gate Status' in md
        assert f'| Total Items | {gate.item_count} |' in md

    def test_blocking_items_in_markdown(self):
        run_log = _make_run_log()
        gate = _make_gate(has_failures=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        md = report.to_markdown()
        assert '### Blocking Gate Items' in md
        assert 'slo_alerts_defined' in md

    def test_no_gate_section_without_gate(self):
        run_log = _make_run_log()
        report = ValidationReport.build(run_log=run_log)
        md = report.to_markdown()
        assert '## Rollout Gate Status' not in md

    def test_conditional_recommendation_text(self):
        run_log = _make_run_log()
        gate = _make_gate(all_pending=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        md = report.to_markdown()
        assert '**CONDITIONAL**' in md
        assert 'pending' in md.lower()

    def test_gate_summary_in_text(self):
        run_log = _make_run_log()
        gate = _make_gate(all_passed=True)
        report = ValidationReport.build(
            run_log=run_log, gate_checklist=gate,
        )
        assert 'Gate:' in report.summary
        assert f'{gate.item_count}' in report.summary


# =====================================================================
# _extract_gate_info helper
# =====================================================================


class TestExtractGateInfo:

    def test_none_gate_returns_empty(self):
        summary, blocking = _extract_gate_info(None)
        assert summary == {}
        assert blocking == []

    def test_all_passed_gate(self):
        gate = _make_gate(all_passed=True)
        summary, blocking = _extract_gate_info(gate)
        assert summary['total'] == gate.item_count
        assert summary['passed'] == gate.item_count
        assert summary['release_blocked'] is False
        assert blocking == []

    def test_failed_gate_extracts_blockers(self):
        gate = _make_gate(has_failures=True)
        summary, blocking = _extract_gate_info(gate)
        assert summary['failed'] >= 1
        assert len(blocking) >= 1
        assert blocking[0]['key'] == 'slo_alerts_defined'
        assert blocking[0]['status'] == 'failed'

    def test_pending_gate_extracts_blockers(self):
        gate = _make_gate(all_pending=True)
        summary, blocking = _extract_gate_info(gate)
        assert summary['pending'] > 0
        assert len(blocking) > 0
        assert all(b['status'] == 'pending' for b in blocking)


# =====================================================================
# _compute_recommendation with gate
# =====================================================================


class TestComputeRecommendationWithGate:

    def test_go_with_gate_passed(self):
        gate = _make_gate(all_passed=True)
        result = _compute_recommendation(
            [], [], 2, gate_checklist=gate,
        )
        assert result == 'GO'

    def test_nogo_with_gate_failure(self):
        gate = _make_gate(has_failures=True)
        result = _compute_recommendation(
            [], [], 2, gate_checklist=gate,
        )
        assert result == 'NO-GO'

    def test_conditional_with_pending_gate(self):
        gate = _make_gate(all_pending=True)
        result = _compute_recommendation(
            [], [], 2, gate_checklist=gate,
        )
        assert result == 'CONDITIONAL'

    def test_scenario_failure_overrides_gate(self):
        gate = _make_gate(all_passed=True)
        result = _compute_recommendation(
            [{'scenario_id': 'S-001'}], [], 2,
            gate_checklist=gate,
        )
        assert result == 'NO-GO'
