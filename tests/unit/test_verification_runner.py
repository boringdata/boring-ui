"""Unit tests for the one-command verification runner."""
import json
from pathlib import Path

import pytest

from boring_ui.api.ci_matrix import (
    MATRIX_SUITES,
    MatrixEnv,
    RunStatus,
    SuiteConfig,
    SuiteType,
)
from boring_ui.api.test_artifacts import EventTimeline, StructuredTestLogger
from boring_ui.api.verification_runner import (
    PhaseResult,
    PhaseStatus,
    VERIFICATION_PHASES,
    VerificationPhase,
    VerificationReport,
    VerificationRunner,
    VerificationVerdict,
)


# ── VerificationVerdict ──


class TestVerificationVerdict:

    def test_values(self):
        assert VerificationVerdict.GO.value == 'go'
        assert VerificationVerdict.NO_GO.value == 'no-go'
        assert VerificationVerdict.INCOMPLETE.value == 'incomplete'


# ── PhaseStatus ──


class TestPhaseStatus:

    def test_values(self):
        assert PhaseStatus.PASSED.value == 'passed'
        assert PhaseStatus.FAILED.value == 'failed'
        assert PhaseStatus.SKIPPED.value == 'skipped'
        assert PhaseStatus.NOT_RUN.value == 'not-run'


# ── VERIFICATION_PHASES ──


class TestVerificationPhases:

    def test_phase_count(self):
        assert len(VERIFICATION_PHASES) == 4

    def test_phase_names(self):
        names = [p.name for p in VERIFICATION_PHASES]
        assert names == ['unit', 'e2e', 'perf', 'smoke']

    def test_required_phases(self):
        required = [p for p in VERIFICATION_PHASES if p.required_for_go]
        assert len(required) == 2
        assert {p.name for p in required} == {'unit', 'e2e'}

    def test_optional_phases(self):
        optional = [p for p in VERIFICATION_PHASES if not p.required_for_go]
        assert len(optional) == 2
        assert {p.name for p in optional} == {'perf', 'smoke'}

    def test_phases_frozen(self):
        phase = VERIFICATION_PHASES[0]
        with pytest.raises(AttributeError):
            phase.name = 'changed'


# ── PhaseResult ──


class TestPhaseResult:

    def _phase(self):
        return VerificationPhase(
            name='unit',
            label='Unit Tests',
            suite_types=(SuiteType.UNIT,),
            env=MatrixEnv.LOCAL,
        )

    def test_empty(self):
        r = PhaseResult(phase=self._phase(), status=PhaseStatus.PASSED)
        assert r.total_tests == 0
        assert r.total_passed == 0
        assert r.total_failed == 0

    def test_to_dict(self):
        r = PhaseResult(phase=self._phase(), status=PhaseStatus.PASSED)
        d = r.to_dict()
        assert d['phase'] == 'unit'
        assert d['label'] == 'Unit Tests'
        assert d['status'] == 'passed'
        assert d['required_for_go'] is True  # default

    def test_to_dict_serializable(self):
        r = PhaseResult(phase=self._phase(), status=PhaseStatus.PASSED)
        json.dumps(r.to_dict())


# ── VerificationReport ──


class TestVerificationReport:

    def _phase(self, name='unit', required=True):
        return VerificationPhase(
            name=name,
            label=name.title(),
            suite_types=(SuiteType.UNIT,),
            env=MatrixEnv.LOCAL,
            required_for_go=required,
        )

    def test_empty_incomplete(self):
        r = VerificationReport(run_id='test-1', started_at=1000.0)
        assert r.verdict == VerificationVerdict.INCOMPLETE

    def test_go_verdict(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            phase_results=[
                PhaseResult(phase=self._phase(), status=PhaseStatus.PASSED),
            ],
        )
        assert r.verdict == VerificationVerdict.GO

    def test_no_go_verdict(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            phase_results=[
                PhaseResult(phase=self._phase(), status=PhaseStatus.FAILED),
            ],
        )
        assert r.verdict == VerificationVerdict.NO_GO

    def test_incomplete_when_not_run(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            phase_results=[
                PhaseResult(phase=self._phase(), status=PhaseStatus.NOT_RUN),
            ],
        )
        assert r.verdict == VerificationVerdict.INCOMPLETE

    def test_optional_failure_doesnt_block_go(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            phase_results=[
                PhaseResult(phase=self._phase(), status=PhaseStatus.PASSED),
                PhaseResult(
                    phase=self._phase('perf', required=False),
                    status=PhaseStatus.FAILED,
                ),
            ],
        )
        assert r.verdict == VerificationVerdict.GO

    def test_elapsed_seconds(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1015.5,
        )
        assert r.elapsed_seconds == 15.5

    def test_totals(self):
        from boring_ui.api.ci_matrix import SuiteResult
        cfg = SuiteConfig(
            suite_type=SuiteType.UNIT,
            env=MatrixEnv.LOCAL,
            label='unit',
            test_path='tests/',
        )
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            phase_results=[
                PhaseResult(
                    phase=self._phase(),
                    status=PhaseStatus.PASSED,
                    suite_results=[
                        SuiteResult(config=cfg, status=RunStatus.PASSED, passed=10, failed=2, skipped=1),
                    ],
                ),
            ],
        )
        assert r.total_tests == 13
        assert r.total_passed == 10
        assert r.total_failed == 2
        assert r.total_skipped == 1

    def test_to_dict(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.0,
            phase_results=[
                PhaseResult(phase=self._phase(), status=PhaseStatus.PASSED),
            ],
        )
        d = r.to_dict()
        assert d['run_id'] == 'test-1'
        assert d['verdict'] == 'go'
        assert len(d['phases']) == 1

    def test_to_dict_with_flaky(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            flaky_summary={'total_tracked': 2},
        )
        d = r.to_dict()
        assert d['flaky_tests'] == {'total_tracked': 2}

    def test_to_dict_with_artifacts(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            artifact_paths={'report': '/tmp/report.json'},
        )
        d = r.to_dict()
        assert d['artifacts'] == {'report': '/tmp/report.json'}

    def test_to_dict_serializable(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.0,
            phase_results=[
                PhaseResult(phase=self._phase(), status=PhaseStatus.PASSED),
            ],
        )
        json.dumps(r.to_dict())

    def test_to_summary_line(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.0,
            phase_results=[
                PhaseResult(phase=self._phase(), status=PhaseStatus.PASSED),
            ],
        )
        line = r.to_summary_line()
        assert 'VERDICT: GO' in line

    def test_to_summary_line_no_go(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.0,
            phase_results=[
                PhaseResult(phase=self._phase(), status=PhaseStatus.FAILED),
            ],
        )
        line = r.to_summary_line()
        assert 'VERDICT: NO-GO' in line

    def test_phase_by_name(self):
        r = VerificationReport(
            run_id='test-1',
            started_at=1000.0,
            phase_results=[
                PhaseResult(phase=self._phase(), status=PhaseStatus.PASSED),
            ],
        )
        assert r.phase_by_name('unit') is not None
        assert r.phase_by_name('nonexistent') is None


# ── VerificationRunner ──


class TestVerificationRunner:

    def _sim_all_pass(self):
        return {
            'unit': {'passed': 100},
            'contract': {'passed': 20},
            'e2e-parity': {'passed': 50},
            'e2e-resilience': {'passed': 30},
            'fault-injection': {'passed': 40},
            'perf': {'passed': 25},
        }

    def test_from_defaults(self):
        runner = VerificationRunner.from_defaults()
        assert runner.run_id.startswith('verify-')

    def test_run_phase_unit(self):
        runner = VerificationRunner()
        phase = VERIFICATION_PHASES[0]  # unit
        result = runner.run_phase(phase, simulate_results={
            'unit': {'passed': 100},
            'contract': {'passed': 20},
        })
        assert result.status == PhaseStatus.PASSED
        assert result.total_passed == 120

    def test_run_phase_e2e(self):
        runner = VerificationRunner()
        phase = VERIFICATION_PHASES[1]  # e2e
        result = runner.run_phase(phase, simulate_results={
            'e2e-parity': {'passed': 50},
            'e2e-resilience': {'passed': 30},
            'fault-injection': {'passed': 40},
        })
        assert result.status == PhaseStatus.PASSED
        assert result.total_passed == 120

    def test_run_phase_failure(self):
        runner = VerificationRunner()
        phase = VERIFICATION_PHASES[0]
        result = runner.run_phase(phase, simulate_results={
            'unit': {'passed': 90, 'failed': 10, 'failures': [
                {'test_name': 'test_bad', 'message': 'assertion'},
            ]},
            'contract': {'passed': 20},
        })
        assert result.status == PhaseStatus.FAILED

    def test_run_phase_smoke_skipped(self):
        runner = VerificationRunner()
        phase = VERIFICATION_PHASES[3]  # smoke
        result = runner.run_phase(phase)
        assert result.status == PhaseStatus.SKIPPED

    def test_run_all_go(self):
        runner = VerificationRunner()
        report = runner.run_all(simulate_results=self._sim_all_pass())
        assert report.verdict == VerificationVerdict.GO
        assert report.total_passed == 265

    def test_run_all_no_go(self):
        runner = VerificationRunner()
        sim = self._sim_all_pass()
        sim['unit'] = {'passed': 90, 'failed': 10, 'failures': [
            {'test_name': 'test_bad', 'message': 'assertion'},
        ]}
        report = runner.run_all(simulate_results=sim)
        assert report.verdict == VerificationVerdict.NO_GO

    def test_run_all_stop_on_required_failure(self):
        runner = VerificationRunner()
        sim = self._sim_all_pass()
        sim['unit'] = {'passed': 0, 'failed': 1, 'failures': [
            {'test_name': 'test_bad', 'message': 'crash'},
        ]}
        report = runner.run_all(
            simulate_results=sim,
            stop_on_required_failure=True,
        )
        assert report.verdict == VerificationVerdict.INCOMPLETE
        not_run = [p for p in report.phase_results if p.status == PhaseStatus.NOT_RUN]
        assert len(not_run) >= 1

    def test_run_all_report_serializable(self):
        runner = VerificationRunner()
        report = runner.run_all(simulate_results=self._sim_all_pass())
        json.dumps(report.to_dict())

    def test_save_bundle(self, tmp_path):
        runner = VerificationRunner()
        report = runner.run_all(simulate_results=self._sim_all_pass())
        paths = runner.save_bundle(report, tmp_path)
        assert 'report' in paths
        assert 'log' in paths
        assert 'timeline' in paths
        assert 'manifest' in paths
        for p in paths.values():
            assert Path(p).exists()

    def test_save_bundle_report_content(self, tmp_path):
        runner = VerificationRunner()
        report = runner.run_all(simulate_results=self._sim_all_pass())
        paths = runner.save_bundle(report, tmp_path)
        data = json.loads(Path(paths['report']).read_text())
        assert data['verdict'] == 'go'

    def test_save_bundle_manifest(self, tmp_path):
        runner = VerificationRunner()
        report = runner.run_all(simulate_results=self._sim_all_pass())
        paths = runner.save_bundle(report, tmp_path)
        manifest = json.loads(Path(paths['manifest']).read_text())
        assert manifest['test_suite'] == 'verification'
        assert manifest['summary']['verdict'] == 'go'

    def test_properties(self):
        runner = VerificationRunner()
        assert runner.logger is not None
        assert runner.timeline is not None
        assert runner.flaky_tracker is not None
        assert runner.phase_results == []

    def test_logger_records(self):
        test_logger = StructuredTestLogger()
        runner = VerificationRunner(logger=test_logger)
        runner.run_phase(VERIFICATION_PHASES[0], simulate_results={
            'unit': {'passed': 10},
            'contract': {'passed': 5},
        })
        assert test_logger.count >= 1

    def test_timeline_records(self):
        timeline = EventTimeline()
        runner = VerificationRunner(timeline=timeline)
        runner.run_phase(VERIFICATION_PHASES[0], simulate_results={
            'unit': {'passed': 10},
            'contract': {'passed': 5},
        })
        assert timeline.count >= 1

    def test_run_all_includes_flaky_summary(self):
        runner = VerificationRunner()
        sim = self._sim_all_pass()
        sim['unit'] = {'passed': 99, 'failed': 1, 'failures': [
            {'test_name': 'test_flaky', 'message': 'intermittent'},
        ]}
        report = runner.run_all(simulate_results=sim)
        assert 'total_tracked' in report.flaky_summary

    def test_run_all_includes_slo_report_when_inputs_provided(self):
        runner = VerificationRunner()
        report = runner.run_all(
            simulate_results=self._sim_all_pass(),
            smoke_summary={
                'results': [{'step': 'readiness', 'outcome': 'pass', 'elapsed_ms': 1000.0}],
            },
            resilience_summary={
                'results': [{'reconnect_attempts': 1, 'outcome': 'recovered', 'recovery_time_ms': 500.0}],
            },
            perf_summary={
                'results': [{'endpoint': 'pty', 'latency': {'p50': 60.0}}],
                'tree_local_p95_ms': 40.0,
                'tree_sandbox_p95_ms': 80.0,
            },
        )
        assert report.slo_report['go_no_go'] == 'go'

    def test_save_bundle_includes_slo_artifact_when_present(self, tmp_path):
        runner = VerificationRunner()
        report = runner.run_all(
            simulate_results=self._sim_all_pass(),
            smoke_summary={
                'results': [{'step': 'readiness', 'outcome': 'pass', 'elapsed_ms': 1000.0}],
            },
            resilience_summary={
                'results': [{'reconnect_attempts': 1, 'outcome': 'recovered', 'recovery_time_ms': 500.0}],
            },
            perf_summary={
                'results': [{'endpoint': 'pty', 'latency': {'p50': 60.0}}],
                'tree_local_p95_ms': 40.0,
                'tree_sandbox_p95_ms': 80.0,
            },
        )
        paths = runner.save_bundle(report, tmp_path)
        assert 'slo_report' in paths
        assert Path(paths['slo_report']).exists()

    def test_run_all_evaluates_slo_when_empty_inputs_provided(self):
        runner = VerificationRunner()
        report = runner.run_all(
            simulate_results=self._sim_all_pass(),
            smoke_summary={},
            resilience_summary={},
            perf_summary={},
        )
        assert report.slo_report['go_no_go'] == 'no-go'

    def test_phase_by_name_after_run(self):
        runner = VerificationRunner()
        report = runner.run_all(simulate_results=self._sim_all_pass())
        unit = report.phase_by_name('unit')
        assert unit is not None
        assert unit.status == PhaseStatus.PASSED

    def test_smoke_skipped_in_full_run(self):
        runner = VerificationRunner()
        report = runner.run_all(simulate_results=self._sim_all_pass())
        smoke = report.phase_by_name('smoke')
        assert smoke is not None
        assert smoke.status == PhaseStatus.SKIPPED
