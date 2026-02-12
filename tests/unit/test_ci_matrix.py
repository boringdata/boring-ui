"""Unit tests for CI matrix wiring and failure-centric reporting."""
import json

import pytest

from boring_ui.api.ci_matrix import (
    CIMatrixReport,
    CIMatrixRunner,
    FlakyTestEntry,
    FlakyTestTracker,
    MatrixEnv,
    MATRIX_SUITES,
    RunStatus,
    SuiteConfig,
    SuiteResult,
    SuiteType,
    TestFailure,
    get_matrix_suites,
)
from boring_ui.api.test_artifacts import EventTimeline, StructuredTestLogger


# ── MatrixEnv ──


class TestMatrixEnv:

    def test_values(self):
        assert MatrixEnv.LOCAL.value == 'local'
        assert MatrixEnv.SANDBOX_STUBBED.value == 'sandbox-stubbed'
        assert MatrixEnv.LIVE_SMOKE.value == 'live-smoke'


# ── SuiteType ──


class TestSuiteType:

    def test_values(self):
        assert SuiteType.UNIT.value == 'unit'
        assert SuiteType.CONTRACT.value == 'contract'
        assert SuiteType.E2E_PARITY.value == 'e2e-parity'
        assert SuiteType.E2E_RESILIENCE.value == 'e2e-resilience'
        assert SuiteType.FAULT_INJECTION.value == 'fault-injection'
        assert SuiteType.PERF.value == 'perf'
        assert SuiteType.SMOKE.value == 'smoke'


# ── RunStatus ──


class TestRunStatus:

    def test_values(self):
        assert RunStatus.PASSED.value == 'passed'
        assert RunStatus.FAILED.value == 'failed'
        assert RunStatus.SKIPPED.value == 'skipped'
        assert RunStatus.ERROR.value == 'error'


# ── SuiteConfig ──


class TestSuiteConfig:

    def test_frozen(self):
        cfg = SuiteConfig(
            suite_type=SuiteType.UNIT,
            env=MatrixEnv.LOCAL,
            label='unit',
            test_path='tests/unit/',
        )
        with pytest.raises(AttributeError):
            cfg.label = 'changed'

    def test_defaults(self):
        cfg = SuiteConfig(
            suite_type=SuiteType.UNIT,
            env=MatrixEnv.LOCAL,
            label='unit',
            test_path='tests/unit/',
        )
        assert cfg.requires_credentials is False
        assert cfg.timeout_seconds == 300
        assert cfg.retry_on_failure is False
        assert cfg.max_retries == 0
        assert cfg.tags == ()

    def test_with_credentials(self):
        cfg = SuiteConfig(
            suite_type=SuiteType.SMOKE,
            env=MatrixEnv.LIVE_SMOKE,
            label='smoke',
            test_path='tests/unit/test_smoke_tests.py',
            requires_credentials=True,
        )
        assert cfg.requires_credentials is True

    def test_with_tags(self):
        cfg = SuiteConfig(
            suite_type=SuiteType.UNIT,
            env=MatrixEnv.LOCAL,
            label='unit',
            test_path='tests/unit/',
            tags=('fast', 'local'),
        )
        assert 'fast' in cfg.tags
        assert 'local' in cfg.tags


# ── MATRIX_SUITES ──


class TestMatrixSuites:

    def test_all_envs_represented(self):
        envs = {s.env for s in MATRIX_SUITES}
        assert MatrixEnv.LOCAL in envs
        assert MatrixEnv.SANDBOX_STUBBED in envs
        assert MatrixEnv.LIVE_SMOKE in envs

    def test_suite_count(self):
        assert len(MATRIX_SUITES) == 7

    def test_local_suites(self):
        local = [s for s in MATRIX_SUITES if s.env == MatrixEnv.LOCAL]
        assert len(local) == 2
        labels = {s.label for s in local}
        assert 'unit' in labels
        assert 'contract' in labels

    def test_sandbox_stubbed_suites(self):
        stubbed = [s for s in MATRIX_SUITES if s.env == MatrixEnv.SANDBOX_STUBBED]
        assert len(stubbed) == 4
        labels = {s.label for s in stubbed}
        assert 'e2e-parity' in labels
        assert 'e2e-resilience' in labels
        assert 'fault-injection' in labels
        assert 'perf' in labels

    def test_live_smoke_requires_credentials(self):
        smoke = [s for s in MATRIX_SUITES if s.env == MatrixEnv.LIVE_SMOKE]
        assert len(smoke) == 1
        assert smoke[0].requires_credentials is True

    def test_all_have_test_paths(self):
        for s in MATRIX_SUITES:
            assert s.test_path


# ── TestFailure ──


class TestTestFailure:

    def test_basic(self):
        f = TestFailure(
            test_name='test_foo',
            suite_label='unit',
            message='assertion failed',
        )
        assert f.test_name == 'test_foo'
        assert f.suite_label == 'unit'

    def test_to_dict_minimal(self):
        f = TestFailure(
            test_name='test_foo',
            suite_label='unit',
            message='boom',
        )
        d = f.to_dict()
        assert d['test_name'] == 'test_foo'
        assert d['message'] == 'boom'
        assert 'request_id' not in d
        assert 'file_path' not in d

    def test_to_dict_full(self):
        f = TestFailure(
            test_name='test_foo',
            suite_label='unit',
            message='boom',
            request_id='req-123',
            file_path='tests/test_foo.py',
            line_number=42,
            elapsed_ms=1.5,
            artifact_path='/tmp/artifact.json',
        )
        d = f.to_dict()
        assert d['request_id'] == 'req-123'
        assert d['file_path'] == 'tests/test_foo.py'
        assert d['line_number'] == 42
        assert d['elapsed_ms'] == 1.5
        assert d['artifact_path'] == '/tmp/artifact.json'

    def test_to_dict_serializable(self):
        f = TestFailure(
            test_name='test_foo',
            suite_label='unit',
            message='boom',
            request_id='req-123',
        )
        json.dumps(f.to_dict())


# ── SuiteResult ──


class TestSuiteResult:

    def _config(self):
        return SuiteConfig(
            suite_type=SuiteType.UNIT,
            env=MatrixEnv.LOCAL,
            label='unit',
            test_path='tests/unit/',
        )

    def test_total(self):
        r = SuiteResult(
            config=self._config(),
            status=RunStatus.PASSED,
            passed=10,
            failed=2,
            skipped=1,
        )
        assert r.total == 13

    def test_success_rate(self):
        r = SuiteResult(
            config=self._config(),
            status=RunStatus.PASSED,
            passed=8,
            failed=2,
        )
        assert r.success_rate == 0.8

    def test_success_rate_zero_total(self):
        r = SuiteResult(config=self._config(), status=RunStatus.SKIPPED)
        assert r.success_rate == 1.0

    def test_first_failure_none(self):
        r = SuiteResult(config=self._config(), status=RunStatus.PASSED)
        assert r.first_failure is None

    def test_first_failure(self):
        failures = [
            TestFailure('test_a', 'unit', 'first'),
            TestFailure('test_b', 'unit', 'second'),
        ]
        r = SuiteResult(
            config=self._config(),
            status=RunStatus.FAILED,
            failed=2,
            failures=failures,
        )
        assert r.first_failure.test_name == 'test_a'

    def test_to_dict(self):
        r = SuiteResult(
            config=self._config(),
            status=RunStatus.PASSED,
            passed=5,
            request_id='req-1',
        )
        d = r.to_dict()
        assert d['suite'] == 'unit'
        assert d['env'] == 'local'
        assert d['status'] == 'passed'
        assert d['passed'] == 5
        assert d['total'] == 5

    def test_to_dict_with_failure(self):
        failures = [TestFailure('test_a', 'unit', 'boom')]
        r = SuiteResult(
            config=self._config(),
            status=RunStatus.FAILED,
            failed=1,
            failures=failures,
        )
        d = r.to_dict()
        assert d['first_failure']['test_name'] == 'test_a'
        assert d['failure_count'] == 1

    def test_to_dict_serializable(self):
        r = SuiteResult(
            config=self._config(),
            status=RunStatus.PASSED,
            passed=10,
        )
        json.dumps(r.to_dict())


# ── FlakyTestEntry ──


class TestFlakyTestEntry:

    def test_defaults(self):
        e = FlakyTestEntry(test_name='test_foo', suite_label='unit')
        assert e.total_runs == 0
        assert e.flake_rate == 0.0
        assert e.is_stabilized is False

    def test_record_pass(self):
        e = FlakyTestEntry(test_name='test_foo', suite_label='unit')
        e.record_failure()
        e.record_pass()
        assert e.total_runs == 2
        assert e.total_failures == 1
        assert e.consecutive_passes == 1

    def test_record_failure_resets_consecutive(self):
        e = FlakyTestEntry(test_name='test_foo', suite_label='unit')
        for _ in range(5):
            e.record_pass()
        e.record_failure()
        assert e.consecutive_passes == 0

    def test_flake_rate(self):
        e = FlakyTestEntry(
            test_name='test_foo',
            suite_label='unit',
            total_runs=10,
            total_failures=3,
        )
        assert e.flake_rate == 0.3

    def test_is_stabilized(self):
        e = FlakyTestEntry(
            test_name='test_foo',
            suite_label='unit',
            consecutive_passes=10,
        )
        assert e.is_stabilized is True

    def test_not_stabilized(self):
        e = FlakyTestEntry(
            test_name='test_foo',
            suite_label='unit',
            consecutive_passes=9,
        )
        assert e.is_stabilized is False

    def test_to_dict(self):
        e = FlakyTestEntry(
            test_name='test_foo',
            suite_label='unit',
            total_runs=20,
            total_failures=4,
            consecutive_passes=5,
        )
        d = e.to_dict()
        assert d['test_name'] == 'test_foo'
        assert d['flake_rate'] == 0.2
        assert d['is_stabilized'] is False

    def test_to_dict_serializable(self):
        e = FlakyTestEntry(test_name='test_foo', suite_label='unit')
        json.dumps(e.to_dict())


# ── FlakyTestTracker ──


class TestFlakyTestTracker:

    def test_empty(self):
        t = FlakyTestTracker()
        assert t.count == 0
        assert t.active_flakes == []
        assert t.stabilized == []

    def test_record_failure_creates_entry(self):
        t = FlakyTestTracker()
        t.record_failure('unit', 'test_foo')
        assert t.count == 1

    def test_record_pass_without_entry_noop(self):
        t = FlakyTestTracker()
        t.record_pass('unit', 'test_foo')
        assert t.count == 0

    def test_record_pass_updates_existing(self):
        t = FlakyTestTracker()
        t.record_failure('unit', 'test_foo')
        t.record_pass('unit', 'test_foo')
        assert t.count == 1
        entry = t.active_flakes[0]
        assert entry.total_runs == 2
        assert entry.consecutive_passes == 1

    def test_active_vs_stabilized(self):
        t = FlakyTestTracker()
        t.record_failure('unit', 'test_a')
        t.record_failure('unit', 'test_b')
        for _ in range(10):
            t.record_pass('unit', 'test_b')
        assert len(t.active_flakes) == 1
        assert t.active_flakes[0].test_name == 'test_a'
        assert len(t.stabilized) == 1
        assert t.stabilized[0].test_name == 'test_b'

    def test_worst_flakes(self):
        t = FlakyTestTracker()
        # 50% flake rate
        t.record_failure('unit', 'test_a')
        t.record_pass('unit', 'test_a')
        # 100% flake rate
        t.record_failure('unit', 'test_b')
        worst = t.worst_flakes(1)
        assert len(worst) == 1
        assert worst[0].test_name == 'test_b'

    def test_to_dict(self):
        t = FlakyTestTracker()
        t.record_failure('unit', 'test_a')
        d = t.to_dict()
        assert d['total_tracked'] == 1
        assert d['active_flakes'] == 1

    def test_to_dict_serializable(self):
        t = FlakyTestTracker()
        t.record_failure('unit', 'test_a')
        json.dumps(t.to_dict())

    def test_save_and_load(self, tmp_path):
        t = FlakyTestTracker()
        t.record_failure('unit', 'test_a')
        t.record_failure('unit', 'test_b')
        t.record_pass('unit', 'test_a')

        path = tmp_path / 'flaky.json'
        t.save(path)

        loaded = FlakyTestTracker.load(path)
        assert loaded.count == 2
        assert loaded.active_flakes[0].test_name in ('test_a', 'test_b')

    def test_load_missing_file(self, tmp_path):
        path = tmp_path / 'missing.json'
        loaded = FlakyTestTracker.load(path)
        assert loaded.count == 0


# ── CIMatrixReport ──


class TestCIMatrixReport:

    def _suite_result(self, label='unit', status=RunStatus.PASSED, **kwargs):
        cfg = SuiteConfig(
            suite_type=SuiteType.UNIT,
            env=MatrixEnv.LOCAL,
            label=label,
            test_path='tests/unit/',
        )
        return SuiteResult(config=cfg, status=status, **kwargs)

    def test_empty(self):
        r = CIMatrixReport(run_id='test-1', started_at=1000.0)
        assert r.overall_status == RunStatus.SKIPPED
        assert r.total_tests == 0

    def test_all_passed(self):
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            suite_results=[
                self._suite_result(passed=10),
                self._suite_result(label='e2e', passed=5),
            ],
        )
        assert r.overall_status == RunStatus.PASSED
        assert r.total_passed == 15
        assert r.total_failed == 0

    def test_any_failed(self):
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            suite_results=[
                self._suite_result(passed=10),
                self._suite_result(
                    label='e2e',
                    status=RunStatus.FAILED,
                    failed=1,
                ),
            ],
        )
        assert r.overall_status == RunStatus.FAILED
        assert r.total_failed == 1

    def test_error_takes_precedence(self):
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            suite_results=[
                self._suite_result(
                    status=RunStatus.FAILED,
                    failed=1,
                ),
                self._suite_result(
                    label='e2e',
                    status=RunStatus.ERROR,
                    errors=1,
                ),
            ],
        )
        assert r.overall_status == RunStatus.ERROR

    def test_all_skipped(self):
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            suite_results=[
                self._suite_result(status=RunStatus.SKIPPED, skipped=5),
            ],
        )
        assert r.overall_status == RunStatus.SKIPPED

    def test_elapsed_seconds(self):
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.5,
        )
        assert r.elapsed_seconds == 10.5

    def test_first_failure(self):
        failures = [TestFailure('test_a', 'unit', 'boom')]
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            suite_results=[
                self._suite_result(passed=10),
                self._suite_result(
                    label='e2e',
                    status=RunStatus.FAILED,
                    failed=1,
                    failures=failures,
                ),
            ],
        )
        assert r.first_failure.test_name == 'test_a'

    def test_all_failures(self):
        f1 = [TestFailure('test_a', 'unit', 'boom')]
        f2 = [TestFailure('test_b', 'e2e', 'crash')]
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            suite_results=[
                self._suite_result(
                    status=RunStatus.FAILED,
                    failed=1,
                    failures=f1,
                ),
                self._suite_result(
                    label='e2e',
                    status=RunStatus.FAILED,
                    failed=1,
                    failures=f2,
                ),
            ],
        )
        assert len(r.all_failures) == 2

    def test_env_results(self):
        cfg_local = SuiteConfig(
            suite_type=SuiteType.UNIT,
            env=MatrixEnv.LOCAL,
            label='unit',
            test_path='tests/',
        )
        cfg_stub = SuiteConfig(
            suite_type=SuiteType.E2E_PARITY,
            env=MatrixEnv.SANDBOX_STUBBED,
            label='e2e',
            test_path='tests/',
        )
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            suite_results=[
                SuiteResult(config=cfg_local, status=RunStatus.PASSED, passed=10),
                SuiteResult(config=cfg_stub, status=RunStatus.PASSED, passed=5),
            ],
        )
        local = r.env_results(MatrixEnv.LOCAL)
        assert len(local) == 1
        stub = r.env_results(MatrixEnv.SANDBOX_STUBBED)
        assert len(stub) == 1

    def test_to_dict(self):
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.0,
            suite_results=[
                self._suite_result(passed=10),
            ],
        )
        d = r.to_dict()
        assert d['run_id'] == 'test-1'
        assert d['status'] == 'passed'
        assert d['total_passed'] == 10
        assert len(d['suites']) == 1

    def test_to_dict_with_first_failure(self):
        failures = [TestFailure('test_a', 'unit', 'boom')]
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            suite_results=[
                self._suite_result(
                    status=RunStatus.FAILED,
                    failed=1,
                    failures=failures,
                ),
            ],
        )
        d = r.to_dict()
        assert 'first_failure' in d
        assert d['first_failure']['test_name'] == 'test_a'

    def test_to_dict_serializable(self):
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.0,
            suite_results=[self._suite_result(passed=10)],
            flaky_summary={'total_tracked': 0},
        )
        json.dumps(r.to_dict())

    def test_to_summary_line_passed(self):
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.0,
            suite_results=[self._suite_result(passed=10)],
        )
        line = r.to_summary_line()
        assert 'PASSED' in line
        assert '10 passed' in line

    def test_to_summary_line_with_failure(self):
        failures = [TestFailure('test_a', 'unit', 'boom')]
        r = CIMatrixReport(
            run_id='test-1',
            started_at=1000.0,
            finished_at=1010.0,
            suite_results=[
                self._suite_result(
                    status=RunStatus.FAILED,
                    passed=9,
                    failed=1,
                    failures=failures,
                ),
            ],
        )
        line = r.to_summary_line()
        assert 'FAILED' in line
        assert 'first failure: test_a' in line


# ── CIMatrixRunner ──


class TestCIMatrixRunner:

    def test_run_suite_passed(self):
        runner = CIMatrixRunner()
        config = MATRIX_SUITES[0]  # unit
        result = runner.run_suite(config, simulate_results={'passed': 10})
        assert result.status == RunStatus.PASSED
        assert result.passed == 10
        assert len(runner.results) == 1

    def test_run_suite_failed(self):
        runner = CIMatrixRunner()
        config = MATRIX_SUITES[0]
        result = runner.run_suite(config, simulate_results={
            'passed': 8,
            'failed': 2,
            'failures': [
                {'test_name': 'test_a', 'message': 'assertion error'},
                {'test_name': 'test_b', 'message': 'type error'},
            ],
        })
        assert result.status == RunStatus.FAILED
        assert result.failed == 2
        assert result.first_failure.test_name == 'test_a'

    def test_run_suite_skips_without_credentials(self):
        runner = CIMatrixRunner()
        smoke_config = [s for s in MATRIX_SUITES if s.requires_credentials][0]
        result = runner.run_suite(smoke_config)
        assert result.status == RunStatus.SKIPPED

    def test_run_suite_with_credentials(self):
        runner = CIMatrixRunner()
        smoke_config = [s for s in MATRIX_SUITES if s.requires_credentials][0]
        result = runner.run_suite(smoke_config, simulate_results={
            'credentials_available': True,
            'passed': 5,
        })
        assert result.status == RunStatus.PASSED

    def test_run_suite_error(self):
        runner = CIMatrixRunner()
        config = MATRIX_SUITES[0]
        result = runner.run_suite(config, simulate_results={
            'passed': 5,
            'errors': 1,
        })
        assert result.status == RunStatus.ERROR

    def test_run_env_local(self):
        runner = CIMatrixRunner()
        results = runner.run_env(
            MatrixEnv.LOCAL,
            simulate_results={
                'unit': {'passed': 100},
                'contract': {'passed': 20},
            },
        )
        assert len(results) == 2

    def test_run_env_sandbox_stubbed(self):
        runner = CIMatrixRunner()
        results = runner.run_env(
            MatrixEnv.SANDBOX_STUBBED,
            simulate_results={
                'e2e-parity': {'passed': 50},
                'e2e-resilience': {'passed': 30},
                'fault-injection': {'passed': 40},
                'perf': {'passed': 25},
            },
        )
        assert len(results) == 4

    def test_run_all(self):
        runner = CIMatrixRunner()
        report = runner.run_all(simulate_results={
            'unit': {'passed': 100},
            'contract': {'passed': 20},
            'e2e-parity': {'passed': 50},
            'e2e-resilience': {'passed': 30},
            'fault-injection': {'passed': 40},
            'perf': {'passed': 25},
        })
        assert report.overall_status == RunStatus.PASSED
        assert report.total_passed == 265
        # Smoke is skipped (no credentials)
        assert report.total_skipped >= 1

    def test_run_all_report_serializable(self):
        runner = CIMatrixRunner()
        report = runner.run_all(simulate_results={
            'unit': {'passed': 10},
            'contract': {'passed': 5},
            'e2e-parity': {'passed': 5},
            'e2e-resilience': {'passed': 5},
            'fault-injection': {'passed': 5},
            'perf': {'passed': 5},
        })
        json.dumps(report.to_dict())

    def test_flaky_tracking_on_failure(self):
        runner = CIMatrixRunner()
        config = MATRIX_SUITES[0]
        runner.run_suite(config, simulate_results={
            'passed': 9,
            'failed': 1,
            'failures': [{'test_name': 'test_flaky', 'message': 'flaky'}],
        })
        assert runner.flaky_tracker.count == 1

    def test_logger_records(self):
        test_logger = StructuredTestLogger()
        runner = CIMatrixRunner(logger=test_logger)
        runner.run_suite(MATRIX_SUITES[0], simulate_results={'passed': 5})
        assert test_logger.count == 1

    def test_timeline_records(self):
        timeline = EventTimeline()
        runner = CIMatrixRunner(timeline=timeline)
        runner.run_suite(MATRIX_SUITES[0], simulate_results={'passed': 5})
        assert timeline.count == 1

    def test_generate_report(self):
        runner = CIMatrixRunner()
        runner.run_suite(MATRIX_SUITES[0], simulate_results={'passed': 10})
        report = runner.generate_report()
        assert report.total_passed == 10

    def test_save_report(self, tmp_path):
        runner = CIMatrixRunner()
        runner.run_suite(MATRIX_SUITES[0], simulate_results={'passed': 10})
        report = runner.generate_report()
        path = runner.save_report(report, tmp_path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data['total_passed'] == 10

    def test_run_id(self):
        runner = CIMatrixRunner()
        assert runner.run_id.startswith('ci-')

    def test_properties(self):
        runner = CIMatrixRunner()
        assert runner.logger is not None
        assert runner.timeline is not None
        assert runner.flaky_tracker is not None

    def test_suites_for_env(self):
        runner = CIMatrixRunner()
        grouped = runner.suites_for_env
        assert MatrixEnv.LOCAL in grouped
        assert MatrixEnv.SANDBOX_STUBBED in grouped
        assert MatrixEnv.LIVE_SMOKE in grouped


# ── get_matrix_suites ──


class TestGetMatrixSuites:

    def test_no_filters(self):
        suites = get_matrix_suites()
        assert len(suites) == len(MATRIX_SUITES)

    def test_filter_by_env(self):
        suites = get_matrix_suites(envs=[MatrixEnv.LOCAL])
        assert all(s.env == MatrixEnv.LOCAL for s in suites)
        assert len(suites) == 2

    def test_filter_by_tags(self):
        suites = get_matrix_suites(tags=['e2e'])
        assert all('e2e' in s.tags for s in suites)

    def test_filter_by_suite_type(self):
        suites = get_matrix_suites(suite_types=[SuiteType.UNIT])
        assert len(suites) == 1
        assert suites[0].suite_type == SuiteType.UNIT

    def test_filter_combined(self):
        suites = get_matrix_suites(
            envs=[MatrixEnv.SANDBOX_STUBBED],
            tags=['e2e'],
        )
        assert all(s.env == MatrixEnv.SANDBOX_STUBBED for s in suites)
        assert all('e2e' in s.tags for s in suites)

    def test_filter_no_match(self):
        suites = get_matrix_suites(tags=['nonexistent'])
        assert len(suites) == 0

    def test_filter_smoke_tag(self):
        suites = get_matrix_suites(tags=['smoke'])
        assert len(suites) == 1
        assert suites[0].suite_type == SuiteType.SMOKE
