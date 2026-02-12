"""Unit tests for V0 SLO measurements and release decision evidence."""
import json
from pathlib import Path

import pytest

from boring_ui.api.perf_e2e import (
    EndpointType,
    LoadProfile,
    LoadTestConfig,
    LoadTestResult,
    simulate_pty_load,
    simulate_search_load,
    simulate_tree_load,
)
from boring_ui.api.fault_injection import FaultInjectionRunner
from boring_ui.api.slo_measurements import (
    ReleaseDecision,
    SLOMeasurement,
    SLOMeasurementRunner,
    SLOReport,
    SLOStatus,
    SLOTarget,
    V0_SLO_TARGETS,
)
from boring_ui.api.test_artifacts import EventTimeline, StructuredTestLogger
from boring_ui.api.verification_runner import VerificationVerdict


# ── SLOStatus ──


class TestSLOStatus:

    def test_values(self):
        assert SLOStatus.MET.value == 'met'
        assert SLOStatus.NOT_MET.value == 'not-met'
        assert SLOStatus.DEGRADED.value == 'degraded'
        assert SLOStatus.NOT_MEASURED.value == 'not-measured'


# ── ReleaseDecision ──


class TestReleaseDecision:

    def test_values(self):
        assert ReleaseDecision.GO.value == 'go'
        assert ReleaseDecision.NO_GO.value == 'no-go'
        assert ReleaseDecision.CONDITIONAL.value == 'conditional'


# ── SLOTarget ──


class TestSLOTarget:

    def test_frozen(self):
        t = V0_SLO_TARGETS[0]
        with pytest.raises(AttributeError):
            t.name = 'changed'

    def test_evaluate_lte_met(self):
        t = SLOTarget(
            name='test', description='test', metric='m',
            threshold=100.0, comparison='lte',
        )
        assert t.evaluate(50.0) == SLOStatus.MET

    def test_evaluate_lte_degraded(self):
        t = SLOTarget(
            name='test', description='test', metric='m',
            threshold=100.0, comparison='lte',
        )
        # 110 is within 1.2x of 100 => degraded
        assert t.evaluate(110.0) == SLOStatus.DEGRADED

    def test_evaluate_lte_not_met(self):
        t = SLOTarget(
            name='test', description='test', metric='m',
            threshold=100.0, comparison='lte',
        )
        assert t.evaluate(150.0) == SLOStatus.NOT_MET

    def test_evaluate_gte_met(self):
        t = SLOTarget(
            name='test', description='test', metric='m',
            threshold=99.0, comparison='gte',
        )
        assert t.evaluate(99.5) == SLOStatus.MET

    def test_evaluate_gte_degraded(self):
        t = SLOTarget(
            name='test', description='test', metric='m',
            threshold=99.0, comparison='gte',
        )
        # 95.0 is >= 99*0.95 = 94.05 => degraded
        assert t.evaluate(95.0) == SLOStatus.DEGRADED

    def test_evaluate_gte_not_met(self):
        t = SLOTarget(
            name='test', description='test', metric='m',
            threshold=99.0, comparison='gte',
        )
        assert t.evaluate(90.0) == SLOStatus.NOT_MET

    def test_evaluate_unknown_comparison(self):
        t = SLOTarget(
            name='test', description='test', metric='m',
            threshold=100.0, comparison='invalid',
        )
        assert t.evaluate(50.0) == SLOStatus.NOT_MEASURED


# ── V0_SLO_TARGETS ──


class TestV0SLOTargets:

    def test_target_count(self):
        assert len(V0_SLO_TARGETS) == 6

    def test_target_names(self):
        names = {t.name for t in V0_SLO_TARGETS}
        assert names == {
            'readiness_latency',
            'pty_median_latency',
            'reattach_success_rate',
            'tree_p95_multiplier',
            'error_rate',
            'fault_tolerance',
        }

    def test_all_required_for_go(self):
        assert all(t.required_for_go for t in V0_SLO_TARGETS)

    def test_readiness_threshold(self):
        t = next(t for t in V0_SLO_TARGETS if t.name == 'readiness_latency')
        assert t.threshold == 5000.0
        assert t.comparison == 'lte'

    def test_pty_threshold(self):
        t = next(t for t in V0_SLO_TARGETS if t.name == 'pty_median_latency')
        assert t.threshold == 150.0

    def test_reattach_threshold(self):
        t = next(t for t in V0_SLO_TARGETS if t.name == 'reattach_success_rate')
        assert t.threshold == 99.0
        assert t.comparison == 'gte'


# ── SLOMeasurement ──


class TestSLOMeasurement:

    def _target(self):
        return SLOTarget(
            name='test', description='test SLO', metric='m',
            threshold=100.0, comparison='lte', unit='ms',
        )

    def test_is_met(self):
        m = SLOMeasurement(
            target=self._target(),
            measured_value=50.0,
            status=SLOStatus.MET,
        )
        assert m.is_met is True
        assert m.is_degraded is False

    def test_is_degraded(self):
        m = SLOMeasurement(
            target=self._target(),
            measured_value=110.0,
            status=SLOStatus.DEGRADED,
        )
        assert m.is_met is False
        assert m.is_degraded is True

    def test_to_dict(self):
        m = SLOMeasurement(
            target=self._target(),
            measured_value=75.0,
            status=SLOStatus.MET,
        )
        d = m.to_dict()
        assert d['name'] == 'test'
        assert d['status'] == 'met'
        assert d['measured'] == 75.0
        assert d['threshold'] == 100.0
        assert d['unit'] == 'ms'

    def test_to_dict_with_details(self):
        m = SLOMeasurement(
            target=self._target(),
            measured_value=75.0,
            status=SLOStatus.MET,
            details={'source': 'perf_test'},
        )
        d = m.to_dict()
        assert d['details'] == {'source': 'perf_test'}

    def test_to_dict_serializable(self):
        m = SLOMeasurement(
            target=self._target(),
            measured_value=75.0,
            status=SLOStatus.MET,
        )
        json.dumps(m.to_dict())


# ── SLOReport ──


class TestSLOReport:

    def _met_measurement(self, name='test', required=True):
        target = SLOTarget(
            name=name, description='test', metric='m',
            threshold=100.0, comparison='lte',
            required_for_go=required,
        )
        return SLOMeasurement(target=target, measured_value=50.0, status=SLOStatus.MET)

    def _not_met_measurement(self, name='test', required=True):
        target = SLOTarget(
            name=name, description='test', metric='m',
            threshold=100.0, comparison='lte',
            required_for_go=required,
        )
        return SLOMeasurement(target=target, measured_value=200.0, status=SLOStatus.NOT_MET)

    def _degraded_measurement(self, name='test', required=True):
        target = SLOTarget(
            name=name, description='test', metric='m',
            threshold=100.0, comparison='lte',
            required_for_go=required,
        )
        return SLOMeasurement(target=target, measured_value=110.0, status=SLOStatus.DEGRADED)

    def test_empty_no_go(self):
        r = SLOReport(run_id='test-1', started_at=1000.0)
        assert r.decision == ReleaseDecision.NO_GO

    def test_all_met_go(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            measurements=[
                self._met_measurement('a'),
                self._met_measurement('b'),
            ],
        )
        assert r.decision == ReleaseDecision.GO
        assert r.met_count == 2

    def test_any_not_met_no_go(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            measurements=[
                self._met_measurement('a'),
                self._not_met_measurement('b'),
            ],
        )
        assert r.decision == ReleaseDecision.NO_GO
        assert r.not_met_count == 1

    def test_degraded_conditional(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            measurements=[
                self._met_measurement('a'),
                self._degraded_measurement('b'),
            ],
        )
        assert r.decision == ReleaseDecision.CONDITIONAL
        assert r.degraded_count == 1

    def test_optional_not_met_still_go(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            measurements=[
                self._met_measurement('a', required=True),
                self._not_met_measurement('b', required=False),
            ],
        )
        assert r.decision == ReleaseDecision.GO

    def test_elapsed_seconds(self):
        r = SLOReport(run_id='test-1', started_at=1000.0, finished_at=1015.0)
        assert r.elapsed_seconds == 15.0

    def test_to_dict(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.0,
            measurements=[self._met_measurement('a')],
        )
        d = r.to_dict()
        assert d['run_id'] == 'test-1'
        assert d['decision'] == 'go'
        assert d['met'] == 1
        assert len(d['measurements']) == 1

    def test_to_dict_with_verification(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            verification_verdict=VerificationVerdict.GO,
            measurements=[self._met_measurement('a')],
        )
        d = r.to_dict()
        assert d['verification_verdict'] == 'go'

    def test_to_dict_serializable(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            measurements=[self._met_measurement('a')],
        )
        json.dumps(r.to_dict())

    def test_to_summary_line_go(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            measurements=[self._met_measurement('a')],
        )
        line = r.to_summary_line()
        assert 'RELEASE: GO' in line

    def test_to_summary_line_no_go(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            measurements=[self._not_met_measurement('a')],
        )
        line = r.to_summary_line()
        assert 'RELEASE: NO-GO' in line

    def test_failing_slos(self):
        r = SLOReport(
            run_id='test-1',
            started_at=1000.0,
            measurements=[
                self._met_measurement('a'),
                self._not_met_measurement('b'),
            ],
        )
        failing = r.failing_slos()
        assert len(failing) == 1
        assert failing[0].target.name == 'b'


# ── SLOMeasurementRunner ──


class TestSLOMeasurementRunner:

    def test_run_id(self):
        runner = SLOMeasurementRunner()
        assert runner.run_id.startswith('slo-')

    def test_properties(self):
        runner = SLOMeasurementRunner()
        assert runner.logger is not None
        assert runner.timeline is not None
        assert runner.measurements == []

    def test_measure_readiness_latency(self):
        runner = SLOMeasurementRunner()
        m = runner.measure_readiness_latency(simulated_ms=500.0)
        assert m.is_met
        assert m.measured_value == 500.0

    def test_measure_readiness_latency_not_met(self):
        runner = SLOMeasurementRunner()
        m = runner.measure_readiness_latency(simulated_ms=10000.0)
        assert m.status == SLOStatus.NOT_MET

    def test_measure_pty_latency(self):
        runner = SLOMeasurementRunner()
        m = runner.measure_pty_latency()
        assert m.status in (SLOStatus.MET, SLOStatus.DEGRADED, SLOStatus.NOT_MET)
        assert m.measured_value > 0

    def test_measure_pty_latency_with_result(self):
        runner = SLOMeasurementRunner()
        load_result = simulate_pty_load()
        m = runner.measure_pty_latency(load_result=load_result)
        assert m.measured_value == load_result.latency.p50

    def test_measure_reattach_success(self):
        runner = SLOMeasurementRunner()
        m = runner.measure_reattach_success(success_rate_pct=99.5)
        assert m.is_met

    def test_measure_reattach_not_met(self):
        runner = SLOMeasurementRunner()
        m = runner.measure_reattach_success(success_rate_pct=90.0)
        assert m.status == SLOStatus.NOT_MET

    def test_measure_tree_p95(self):
        runner = SLOMeasurementRunner()
        m = runner.measure_tree_p95()
        # Same config for local and sandbox => multiplier ~1.0
        assert m.status == SLOStatus.MET
        assert m.measured_value == pytest.approx(1.0, abs=0.1)

    def test_measure_error_rate(self):
        runner = SLOMeasurementRunner()
        m = runner.measure_error_rate()
        assert m.status in (SLOStatus.MET, SLOStatus.DEGRADED, SLOStatus.NOT_MET)
        assert m.measured_value >= 0

    def test_measure_fault_tolerance(self):
        runner = SLOMeasurementRunner()
        m = runner.measure_fault_tolerance()
        assert m.is_met
        assert m.measured_value == 100.0

    def test_run_all(self):
        runner = SLOMeasurementRunner()
        report = runner.run_all()
        assert len(report.measurements) == 6
        assert report.decision in (
            ReleaseDecision.GO,
            ReleaseDecision.CONDITIONAL,
            ReleaseDecision.NO_GO,
        )

    def test_run_all_serializable(self):
        runner = SLOMeasurementRunner()
        report = runner.run_all()
        json.dumps(report.to_dict())

    def test_generate_report(self):
        runner = SLOMeasurementRunner()
        runner.measure_readiness_latency(simulated_ms=100.0)
        report = runner.generate_report()
        assert len(report.measurements) == 1

    def test_save_report(self, tmp_path):
        runner = SLOMeasurementRunner()
        report = runner.run_all()
        paths = runner.save_report(report, tmp_path)
        assert 'report' in paths
        assert 'log' in paths
        assert 'timeline' in paths
        assert 'manifest' in paths
        for p in paths.values():
            assert Path(p).exists()

    def test_save_report_content(self, tmp_path):
        runner = SLOMeasurementRunner()
        report = runner.run_all()
        paths = runner.save_report(report, tmp_path)
        data = json.loads(Path(paths['report']).read_text())
        assert 'decision' in data
        assert 'measurements' in data
        assert len(data['measurements']) == 6

    def test_save_report_manifest(self, tmp_path):
        runner = SLOMeasurementRunner()
        report = runner.run_all()
        paths = runner.save_report(report, tmp_path)
        manifest = json.loads(Path(paths['manifest']).read_text())
        assert manifest['test_suite'] == 'slo-measurements'

    def test_logger_records(self):
        test_logger = StructuredTestLogger()
        runner = SLOMeasurementRunner(logger=test_logger)
        runner.measure_readiness_latency(simulated_ms=100.0)
        assert test_logger.count == 1

    def test_timeline_records(self):
        timeline = EventTimeline()
        runner = SLOMeasurementRunner(timeline=timeline)
        runner.measure_readiness_latency(simulated_ms=100.0)
        assert timeline.count == 1

    def test_custom_targets(self):
        targets = [
            SLOTarget(
                name='readiness_latency',
                description='test',
                metric='m',
                threshold=1000.0,
                comparison='lte',
            ),
        ]
        runner = SLOMeasurementRunner(targets=targets)
        m = runner.measure_readiness_latency(simulated_ms=500.0)
        assert m.is_met
