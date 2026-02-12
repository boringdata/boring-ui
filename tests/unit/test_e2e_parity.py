"""Unit tests for end-to-end parity scripts (local vs sandbox).

Tests the parity comparison engine, scenario runners, journey definitions,
and report generation without requiring live services.
"""
import json

import pytest

from boring_ui.api.e2e_parity import (
    ALL_JOURNEYS,
    CHAT_JOURNEY_STEPS,
    FILE_JOURNEY_STEPS,
    GIT_JOURNEY_STEPS,
    PTY_JOURNEY_STEPS,
    SESSION_JOURNEY_STEPS,
    JourneyStep,
    JourneyType,
    ParityCheck,
    ParityReport,
    ParityRunner,
    ParityVerdict,
    ScenarioRunner,
    StepOutcome,
    StepResult,
    build_parity_report,
    compare_error_categories,
    compare_outcome,
    compare_response_shapes,
    compare_status_codes,
    compare_step_results,
    compare_ws_close_codes,
    compare_ws_message_types,
)
from boring_ui.api.test_artifacts import EventTimeline, StructuredTestLogger


# ── JourneyStep ──


class TestJourneyStep:

    def test_frozen(self):
        step = JourneyStep('test', 'test step', JourneyType.HTTP_FILES, 0)
        with pytest.raises(AttributeError):
            step.name = 'changed'

    def test_fields(self):
        step = JourneyStep('list_tree', 'List files', JourneyType.HTTP_FILES, 0)
        assert step.name == 'list_tree'
        assert step.description == 'List files'
        assert step.journey_type == JourneyType.HTTP_FILES
        assert step.order == 0


# ── StepResult ──


class TestStepResult:

    def _make_step(self, name='test_step'):
        return JourneyStep(name, 'desc', JourneyType.HTTP_FILES, 0)

    def test_success(self):
        result = StepResult(
            step=self._make_step(),
            outcome=StepOutcome.SUCCESS,
            response_status=200,
        )
        assert result.is_success
        assert result.outcome == StepOutcome.SUCCESS

    def test_error(self):
        result = StepResult(
            step=self._make_step(),
            outcome=StepOutcome.ERROR,
            error_message='fail',
        )
        assert not result.is_success
        assert result.error_message == 'fail'

    def test_to_dict_minimal(self):
        result = StepResult(
            step=self._make_step('x'),
            outcome=StepOutcome.SUCCESS,
        )
        d = result.to_dict()
        assert d['step_name'] == 'x'
        assert d['outcome'] == 'success'
        assert 'response_status' not in d
        assert 'ws_close_code' not in d

    def test_to_dict_with_status(self):
        result = StepResult(
            step=self._make_step(),
            outcome=StepOutcome.SUCCESS,
            response_status=200,
            response_shape={'entries': [], 'path': '.'},
        )
        d = result.to_dict()
        assert d['response_status'] == 200
        assert d['response_shape'] == {'entries': [], 'path': '.'}

    def test_to_dict_with_ws(self):
        result = StepResult(
            step=self._make_step(),
            outcome=StepOutcome.SUCCESS,
            ws_close_code=4001,
            ws_messages=[{'type': 'output'}],
        )
        d = result.to_dict()
        assert d['ws_close_code'] == 4001
        assert d['ws_message_count'] == 1

    def test_to_dict_with_error(self):
        result = StepResult(
            step=self._make_step(),
            outcome=StepOutcome.ERROR,
            error_message='timeout',
        )
        d = result.to_dict()
        assert d['error'] == 'timeout'

    def test_to_dict_with_extra(self):
        result = StepResult(
            step=self._make_step(),
            outcome=StepOutcome.SUCCESS,
            extra={'bytes_written': 42},
        )
        d = result.to_dict()
        assert d['extra'] == {'bytes_written': 42}


# ── ParityCheck ──


class TestParityCheck:

    def test_pass(self):
        check = ParityCheck(
            field_name='status',
            local_value='200',
            sandbox_value='200',
            verdict=ParityVerdict.PASS,
        )
        assert check.verdict == ParityVerdict.PASS

    def test_fail_with_message(self):
        check = ParityCheck(
            field_name='status',
            local_value='200',
            sandbox_value='502',
            verdict=ParityVerdict.FAIL,
            message='Status mismatch',
        )
        assert check.verdict == ParityVerdict.FAIL
        assert 'mismatch' in check.message

    def test_to_dict(self):
        check = ParityCheck(
            field_name='status',
            local_value='200',
            sandbox_value='200',
            verdict=ParityVerdict.PASS,
        )
        d = check.to_dict()
        assert d['field'] == 'status'
        assert d['verdict'] == 'pass'
        assert d['local'] == '200'
        assert d['sandbox'] == '200'


# ── ParityReport ──


class TestParityReport:

    def _make_check(self, verdict):
        return ParityCheck('f', '1', '1', verdict)

    def test_all_pass(self):
        report = ParityReport(
            journey_type=JourneyType.HTTP_FILES,
            checks=[self._make_check(ParityVerdict.PASS)] * 3,
        )
        assert report.pass_count == 3
        assert report.fail_count == 0
        assert report.warn_count == 0
        assert report.is_passing

    def test_with_failures(self):
        report = ParityReport(
            journey_type=JourneyType.HTTP_FILES,
            checks=[
                self._make_check(ParityVerdict.PASS),
                self._make_check(ParityVerdict.FAIL),
                self._make_check(ParityVerdict.WARN),
            ],
        )
        assert report.pass_count == 1
        assert report.fail_count == 1
        assert report.warn_count == 1
        assert not report.is_passing

    def test_total_checks(self):
        report = ParityReport(
            journey_type=JourneyType.WS_PTY,
            checks=[self._make_check(ParityVerdict.PASS)] * 5,
        )
        assert report.total_checks == 5

    def test_to_dict(self):
        report = ParityReport(
            journey_type=JourneyType.HTTP_GIT,
            checks=[self._make_check(ParityVerdict.PASS)],
        )
        d = report.to_dict()
        assert d['journey_type'] == 'http_git'
        assert d['total_checks'] == 1
        assert d['is_passing'] is True
        assert len(d['checks']) == 1

    def test_empty(self):
        report = ParityReport(journey_type=JourneyType.HTTP_FILES)
        assert report.is_passing
        assert report.total_checks == 0


# ── Comparison functions ──


class TestCompareStatusCodes:

    def _make_result(self, status):
        step = JourneyStep('s', 'd', JourneyType.HTTP_FILES, 0)
        return StepResult(step=step, outcome=StepOutcome.SUCCESS, response_status=status)

    def test_match(self):
        check = compare_status_codes(self._make_result(200), self._make_result(200))
        assert check.verdict == ParityVerdict.PASS

    def test_mismatch(self):
        check = compare_status_codes(self._make_result(200), self._make_result(404))
        assert check.verdict == ParityVerdict.FAIL
        assert '200' in check.message
        assert '404' in check.message

    def test_field_name(self):
        check = compare_status_codes(self._make_result(200), self._make_result(200))
        assert check.field_name == 'http_status'


class TestCompareResponseShapes:

    def _make_result(self, shape):
        step = JourneyStep('s', 'd', JourneyType.HTTP_FILES, 0)
        return StepResult(step=step, outcome=StepOutcome.SUCCESS, response_shape=shape)

    def test_match(self):
        shape = {'entries': [], 'path': '.'}
        check = compare_response_shapes(
            self._make_result(shape), self._make_result(shape),
        )
        assert check.verdict == ParityVerdict.PASS

    def test_mismatch_missing(self):
        local = {'entries': [], 'path': '.', 'extra': True}
        sandbox = {'entries': [], 'path': '.'}
        check = compare_response_shapes(
            self._make_result(local), self._make_result(sandbox),
        )
        assert check.verdict == ParityVerdict.FAIL
        assert 'missing in sandbox' in check.message

    def test_mismatch_extra(self):
        local = {'entries': []}
        sandbox = {'entries': [], 'bonus': True}
        check = compare_response_shapes(
            self._make_result(local), self._make_result(sandbox),
        )
        assert check.verdict == ParityVerdict.FAIL
        assert 'extra in sandbox' in check.message

    def test_empty_shapes_match(self):
        check = compare_response_shapes(
            self._make_result({}), self._make_result({}),
        )
        assert check.verdict == ParityVerdict.PASS


class TestCompareWsCloseCodes:

    def _make_result(self, code):
        step = JourneyStep('s', 'd', JourneyType.WS_PTY, 0)
        return StepResult(step=step, outcome=StepOutcome.SUCCESS, ws_close_code=code)

    def test_match(self):
        check = compare_ws_close_codes(self._make_result(4001), self._make_result(4001))
        assert check.verdict == ParityVerdict.PASS

    def test_mismatch(self):
        check = compare_ws_close_codes(self._make_result(4001), self._make_result(1011))
        assert check.verdict == ParityVerdict.FAIL


class TestCompareWsMessageTypes:

    def _make_result(self, messages):
        step = JourneyStep('s', 'd', JourneyType.WS_PTY, 0)
        return StepResult(step=step, outcome=StepOutcome.SUCCESS, ws_messages=messages)

    def test_match(self):
        msgs = [{'type': 'output'}, {'type': 'exit'}]
        check = compare_ws_message_types(
            self._make_result(msgs), self._make_result(msgs),
        )
        assert check.verdict == ParityVerdict.PASS

    def test_mismatch(self):
        local = [{'type': 'output'}, {'type': 'exit'}]
        sandbox = [{'type': 'output'}, {'type': 'error'}]
        check = compare_ws_message_types(
            self._make_result(local), self._make_result(sandbox),
        )
        assert check.verdict == ParityVerdict.FAIL

    def test_empty_match(self):
        check = compare_ws_message_types(
            self._make_result([]), self._make_result([]),
        )
        assert check.verdict == ParityVerdict.PASS


class TestCompareErrorCategories:

    def _make_result(self, shape):
        step = JourneyStep('s', 'd', JourneyType.HTTP_FILES, 0)
        return StepResult(step=step, outcome=StepOutcome.SUCCESS, response_shape=shape)

    def test_match(self):
        check = compare_error_categories(
            self._make_result({'category': 'provider'}),
            self._make_result({'category': 'provider'}),
        )
        assert check.verdict == ParityVerdict.PASS

    def test_mismatch(self):
        check = compare_error_categories(
            self._make_result({'category': 'provider'}),
            self._make_result({'category': 'internal'}),
        )
        assert check.verdict == ParityVerdict.FAIL
        assert 'provider' in check.message
        assert 'internal' in check.message

    def test_no_category(self):
        check = compare_error_categories(
            self._make_result({}),
            self._make_result({}),
        )
        assert check.verdict == ParityVerdict.PASS


class TestCompareOutcome:

    def _make_result(self, outcome):
        step = JourneyStep('s', 'd', JourneyType.HTTP_FILES, 0)
        return StepResult(step=step, outcome=outcome)

    def test_match(self):
        check = compare_outcome(
            self._make_result(StepOutcome.SUCCESS),
            self._make_result(StepOutcome.SUCCESS),
        )
        assert check.verdict == ParityVerdict.PASS

    def test_mismatch(self):
        check = compare_outcome(
            self._make_result(StepOutcome.SUCCESS),
            self._make_result(StepOutcome.ERROR),
        )
        assert check.verdict == ParityVerdict.FAIL


# ── compare_step_results ──


class TestCompareStepResults:

    def _step(self):
        return JourneyStep('s', 'd', JourneyType.HTTP_FILES, 0)

    def test_outcome_only(self):
        local = StepResult(step=self._step(), outcome=StepOutcome.SUCCESS)
        sandbox = StepResult(step=self._step(), outcome=StepOutcome.SUCCESS)
        checks = compare_step_results(local, sandbox)
        assert len(checks) == 1  # Only outcome check
        assert checks[0].field_name == 'outcome'

    def test_with_status(self):
        local = StepResult(
            step=self._step(), outcome=StepOutcome.SUCCESS, response_status=200,
        )
        sandbox = StepResult(
            step=self._step(), outcome=StepOutcome.SUCCESS, response_status=200,
        )
        checks = compare_step_results(local, sandbox)
        field_names = {c.field_name for c in checks}
        assert 'outcome' in field_names
        assert 'http_status' in field_names

    def test_with_shapes_and_category(self):
        shape = {'error': 'bad', 'category': 'client'}
        local = StepResult(
            step=self._step(), outcome=StepOutcome.SUCCESS,
            response_status=400, response_shape=shape,
        )
        sandbox = StepResult(
            step=self._step(), outcome=StepOutcome.SUCCESS,
            response_status=400, response_shape=shape,
        )
        checks = compare_step_results(local, sandbox)
        field_names = {c.field_name for c in checks}
        assert 'response_shape' in field_names
        assert 'error_category' in field_names

    def test_with_ws_close(self):
        step = JourneyStep('s', 'd', JourneyType.WS_PTY, 0)
        local = StepResult(step=step, outcome=StepOutcome.SUCCESS, ws_close_code=4001)
        sandbox = StepResult(step=step, outcome=StepOutcome.SUCCESS, ws_close_code=4001)
        checks = compare_step_results(local, sandbox)
        field_names = {c.field_name for c in checks}
        assert 'ws_close_code' in field_names

    def test_with_ws_messages(self):
        step = JourneyStep('s', 'd', JourneyType.WS_PTY, 0)
        msgs = [{'type': 'output'}]
        local = StepResult(step=step, outcome=StepOutcome.SUCCESS, ws_messages=msgs)
        sandbox = StepResult(step=step, outcome=StepOutcome.SUCCESS, ws_messages=msgs)
        checks = compare_step_results(local, sandbox)
        field_names = {c.field_name for c in checks}
        assert 'ws_message_types' in field_names


# ── build_parity_report ──


class TestBuildParityReport:

    def _step(self, name, jtype):
        return JourneyStep(name, 'desc', jtype, 0)

    def test_matching_results(self):
        step = self._step('list_tree', JourneyType.HTTP_FILES)
        local = [StepResult(step=step, outcome=StepOutcome.SUCCESS, response_status=200)]
        sandbox = [StepResult(step=step, outcome=StepOutcome.SUCCESS, response_status=200)]
        report = build_parity_report(JourneyType.HTTP_FILES, local, sandbox)
        assert report.is_passing
        assert report.fail_count == 0

    def test_mismatched_results(self):
        step = self._step('list_tree', JourneyType.HTTP_FILES)
        local = [StepResult(step=step, outcome=StepOutcome.SUCCESS, response_status=200)]
        sandbox = [StepResult(step=step, outcome=StepOutcome.SUCCESS, response_status=404)]
        report = build_parity_report(JourneyType.HTTP_FILES, local, sandbox)
        assert not report.is_passing
        assert report.fail_count > 0

    def test_empty_results(self):
        report = build_parity_report(JourneyType.HTTP_FILES, [], [])
        assert report.is_passing
        assert report.total_checks == 0

    def test_multiple_steps(self):
        steps = [
            self._step('a', JourneyType.HTTP_FILES),
            self._step('b', JourneyType.HTTP_FILES),
        ]
        local = [
            StepResult(step=steps[0], outcome=StepOutcome.SUCCESS, response_status=200),
            StepResult(step=steps[1], outcome=StepOutcome.SUCCESS, response_status=200),
        ]
        sandbox = [
            StepResult(step=steps[0], outcome=StepOutcome.SUCCESS, response_status=200),
            StepResult(step=steps[1], outcome=StepOutcome.SUCCESS, response_status=200),
        ]
        report = build_parity_report(JourneyType.HTTP_FILES, local, sandbox)
        assert report.is_passing
        assert report.total_checks > 0


# ── Journey definitions ──


class TestJourneyDefinitions:

    def test_all_journeys_keys(self):
        expected = {
            JourneyType.HTTP_FILES,
            JourneyType.HTTP_GIT,
            JourneyType.HTTP_SESSIONS,
            JourneyType.WS_PTY,
            JourneyType.WS_CHAT,
        }
        assert set(ALL_JOURNEYS.keys()) == expected

    def test_file_journey_ordered(self):
        orders = [s.order for s in FILE_JOURNEY_STEPS]
        assert orders == sorted(orders)

    def test_git_journey_ordered(self):
        orders = [s.order for s in GIT_JOURNEY_STEPS]
        assert orders == sorted(orders)

    def test_session_journey_ordered(self):
        orders = [s.order for s in SESSION_JOURNEY_STEPS]
        assert orders == sorted(orders)

    def test_pty_journey_ordered(self):
        orders = [s.order for s in PTY_JOURNEY_STEPS]
        assert orders == sorted(orders)

    def test_chat_journey_ordered(self):
        orders = [s.order for s in CHAT_JOURNEY_STEPS]
        assert orders == sorted(orders)

    def test_file_journey_type_consistent(self):
        for step in FILE_JOURNEY_STEPS:
            assert step.journey_type == JourneyType.HTTP_FILES

    def test_git_journey_type_consistent(self):
        for step in GIT_JOURNEY_STEPS:
            assert step.journey_type == JourneyType.HTTP_GIT

    def test_session_journey_type_consistent(self):
        for step in SESSION_JOURNEY_STEPS:
            assert step.journey_type == JourneyType.HTTP_SESSIONS

    def test_pty_journey_type_consistent(self):
        for step in PTY_JOURNEY_STEPS:
            assert step.journey_type == JourneyType.WS_PTY

    def test_chat_journey_type_consistent(self):
        for step in CHAT_JOURNEY_STEPS:
            assert step.journey_type == JourneyType.WS_CHAT

    def test_unique_step_names_per_journey(self):
        for jtype, steps in ALL_JOURNEYS.items():
            names = [s.name for s in steps]
            assert len(names) == len(set(names)), f'Duplicate names in {jtype}'

    def test_file_journey_steps(self):
        names = [s.name for s in FILE_JOURNEY_STEPS]
        assert 'list_tree' in names
        assert 'read_file' in names
        assert 'write_file' in names
        assert 'delete_file' in names

    def test_pty_journey_steps(self):
        names = [s.name for s in PTY_JOURNEY_STEPS]
        assert 'pty_connect' in names
        assert 'pty_input' in names
        assert 'pty_exit' in names

    def test_chat_journey_steps(self):
        names = [s.name for s in CHAT_JOURNEY_STEPS]
        assert 'chat_connect' in names
        assert 'chat_user_msg' in names
        assert 'chat_interrupt' in names


# ── ScenarioRunner ──


class TestScenarioRunner:

    def _step(self, name='test_step', jtype=JourneyType.HTTP_FILES):
        return JourneyStep(name, 'desc', jtype, 0)

    def test_default_mode(self):
        runner = ScenarioRunner()
        assert runner.mode == 'local'

    def test_custom_mode(self):
        runner = ScenarioRunner(mode='sandbox')
        assert runner.mode == 'sandbox'

    def test_execute_step_success(self):
        runner = ScenarioRunner()
        result = runner.execute_step(
            self._step(),
            response_status=200,
            response_shape={'entries': []},
        )
        assert result.is_success
        assert result.response_status == 200
        assert result.request_id  # Generated
        assert result.elapsed_ms >= 0

    def test_execute_step_error(self):
        runner = ScenarioRunner()
        result = runner.execute_step(
            self._step(),
            response_status=500,
            error_message='timeout',
        )
        assert not result.is_success
        assert result.outcome == StepOutcome.ERROR

    def test_results_accumulated(self):
        runner = ScenarioRunner()
        runner.execute_step(self._step('a'))
        runner.execute_step(self._step('b'))
        assert len(runner.results) == 2

    def test_clear(self):
        runner = ScenarioRunner()
        runner.execute_step(self._step())
        runner.clear()
        assert len(runner.results) == 0

    def test_skip_step(self):
        runner = ScenarioRunner()
        result = runner.skip_step(self._step(), reason='not applicable')
        assert result.outcome == StepOutcome.SKIPPED
        assert 'not applicable' in result.error_message

    def test_logger_records(self):
        test_logger = StructuredTestLogger()
        runner = ScenarioRunner(logger=test_logger)
        runner.execute_step(self._step())
        assert test_logger.count == 1

    def test_timeline_records(self):
        timeline = EventTimeline()
        runner = ScenarioRunner(timeline=timeline)
        runner.execute_step(self._step())
        assert timeline.count == 1

    def test_ws_step_timeline_direction(self):
        timeline = EventTimeline()
        runner = ScenarioRunner(timeline=timeline)
        runner.execute_step(self._step(jtype=JourneyType.WS_PTY))
        event = timeline.events[0]
        assert event.direction == 'outbound'
        assert event.event_type == 'ws_message'

    def test_http_step_timeline_direction(self):
        timeline = EventTimeline()
        runner = ScenarioRunner(timeline=timeline)
        runner.execute_step(self._step(jtype=JourneyType.HTTP_FILES))
        event = timeline.events[0]
        assert event.direction == 'inbound'
        assert event.event_type == 'http_request'

    def test_request_id_correlation(self):
        test_logger = StructuredTestLogger()
        timeline = EventTimeline()
        runner = ScenarioRunner(logger=test_logger, timeline=timeline)
        result = runner.execute_step(self._step())
        # Logger and timeline should have the same request_id
        log_entry = test_logger.entries[0]
        timeline_event = timeline.events[0]
        assert log_entry.request_id == result.request_id
        assert timeline_event.request_id == result.request_id

    def test_execute_ws_with_messages(self):
        runner = ScenarioRunner()
        msgs = [{'type': 'output', 'data': 'hello'}]
        result = runner.execute_step(
            self._step(jtype=JourneyType.WS_PTY),
            ws_messages=msgs,
            ws_close_code=4001,
        )
        assert result.ws_close_code == 4001
        assert len(result.ws_messages) == 1


# ── ParityRunner ──


class TestParityRunner:

    def _step(self, name, jtype=JourneyType.HTTP_FILES):
        return JourneyStep(name, 'desc', jtype, 0)

    def test_compare_matching_journeys(self):
        pr = ParityRunner()
        step = self._step('list_tree')
        pr.local_runner.execute_step(step, response_status=200)
        pr.sandbox_runner.execute_step(step, response_status=200)
        report = pr.compare_journey(JourneyType.HTTP_FILES)
        assert report.is_passing

    def test_compare_mismatched_journeys(self):
        pr = ParityRunner()
        step = self._step('list_tree')
        pr.local_runner.execute_step(step, response_status=200)
        pr.sandbox_runner.execute_step(step, response_status=404)
        report = pr.compare_journey(JourneyType.HTTP_FILES)
        assert not report.is_passing

    def test_all_passing(self):
        pr = ParityRunner()
        step = self._step('s')
        pr.local_runner.execute_step(step, response_status=200)
        pr.sandbox_runner.execute_step(step, response_status=200)
        pr.compare_journey(JourneyType.HTTP_FILES)
        assert pr.all_passing

    def test_total_checks(self):
        pr = ParityRunner()
        step = self._step('s')
        pr.local_runner.execute_step(step, response_status=200)
        pr.sandbox_runner.execute_step(step, response_status=200)
        pr.compare_journey(JourneyType.HTTP_FILES)
        assert pr.total_checks > 0

    def test_total_failures(self):
        pr = ParityRunner()
        step = self._step('s')
        pr.local_runner.execute_step(step, response_status=200)
        pr.sandbox_runner.execute_step(step, response_status=500)
        pr.compare_journey(JourneyType.HTTP_FILES)
        assert pr.total_failures > 0

    def test_reports_accumulated(self):
        pr = ParityRunner()
        step_f = self._step('s', JourneyType.HTTP_FILES)
        step_g = self._step('s', JourneyType.HTTP_GIT)
        pr.local_runner.execute_step(step_f, response_status=200)
        pr.sandbox_runner.execute_step(step_f, response_status=200)
        pr.local_runner.execute_step(step_g, response_status=200)
        pr.sandbox_runner.execute_step(step_g, response_status=200)
        pr.compare_journey(JourneyType.HTTP_FILES)
        pr.compare_journey(JourneyType.HTTP_GIT)
        assert len(pr.reports) == 2

    def test_summary(self):
        pr = ParityRunner()
        step = self._step('s')
        pr.local_runner.execute_step(step, response_status=200)
        pr.sandbox_runner.execute_step(step, response_status=200)
        pr.compare_journey(JourneyType.HTTP_FILES)
        summary = pr.summary()
        assert summary['total_journeys'] == 1
        assert summary['all_passing'] is True
        assert 'journeys' in summary

    def test_summary_serializable(self):
        pr = ParityRunner()
        step = self._step('s')
        pr.local_runner.execute_step(step, response_status=200)
        pr.sandbox_runner.execute_step(step, response_status=200)
        pr.compare_journey(JourneyType.HTTP_FILES)
        # Should be JSON-serializable
        json.dumps(pr.summary())

    def test_custom_runners(self):
        local = ScenarioRunner(mode='local')
        sandbox = ScenarioRunner(mode='sandbox')
        pr = ParityRunner(local_runner=local, sandbox_runner=sandbox)
        assert pr.local_runner.mode == 'local'
        assert pr.sandbox_runner.mode == 'sandbox'


# ── Full journey simulation ──


class TestFullJourneySimulation:
    """Simulate complete user journeys and verify parity checking works end-to-end."""

    def test_file_journey_parity(self):
        pr = ParityRunner()
        for step in FILE_JOURNEY_STEPS:
            pr.local_runner.execute_step(step, response_status=200, response_shape={'entries': []})
            pr.sandbox_runner.execute_step(step, response_status=200, response_shape={'entries': []})
        report = pr.compare_journey(JourneyType.HTTP_FILES)
        assert report.is_passing
        assert report.total_checks > 0

    def test_git_journey_parity(self):
        pr = ParityRunner()
        for step in GIT_JOURNEY_STEPS:
            pr.local_runner.execute_step(step, response_status=200)
            pr.sandbox_runner.execute_step(step, response_status=200)
        report = pr.compare_journey(JourneyType.HTTP_GIT)
        assert report.is_passing

    def test_session_journey_parity(self):
        pr = ParityRunner()
        for step in SESSION_JOURNEY_STEPS:
            pr.local_runner.execute_step(step, response_status=200)
            pr.sandbox_runner.execute_step(step, response_status=200)
        report = pr.compare_journey(JourneyType.HTTP_SESSIONS)
        assert report.is_passing

    def test_pty_journey_parity(self):
        pr = ParityRunner()
        for step in PTY_JOURNEY_STEPS:
            pr.local_runner.execute_step(
                step,
                ws_messages=[{'type': 'output'}],
                ws_close_code=1000,
            )
            pr.sandbox_runner.execute_step(
                step,
                ws_messages=[{'type': 'output'}],
                ws_close_code=1000,
            )
        report = pr.compare_journey(JourneyType.WS_PTY)
        assert report.is_passing

    def test_chat_journey_parity(self):
        pr = ParityRunner()
        for step in CHAT_JOURNEY_STEPS:
            pr.local_runner.execute_step(
                step,
                ws_messages=[{'type': 'system', 'subtype': 'connected'}],
                ws_close_code=1000,
            )
            pr.sandbox_runner.execute_step(
                step,
                ws_messages=[{'type': 'system', 'subtype': 'connected'}],
                ws_close_code=1000,
            )
        report = pr.compare_journey(JourneyType.WS_CHAT)
        assert report.is_passing

    def test_divergence_detected(self):
        """Verify divergence in sandbox is properly detected."""
        pr = ParityRunner()
        step = FILE_JOURNEY_STEPS[0]  # list_tree
        pr.local_runner.execute_step(
            step,
            response_status=200,
            response_shape={'entries': [], 'path': '.'},
        )
        pr.sandbox_runner.execute_step(
            step,
            response_status=502,
            response_shape={'error': 'upstream timeout', 'category': 'provider'},
        )
        report = pr.compare_journey(JourneyType.HTTP_FILES)
        assert not report.is_passing
        assert report.fail_count >= 1

    def test_ws_close_code_divergence(self):
        """Verify WS close code divergence is detected."""
        pr = ParityRunner()
        step = PTY_JOURNEY_STEPS[-1]  # pty_exit
        pr.local_runner.execute_step(step, ws_close_code=1000)
        pr.sandbox_runner.execute_step(step, ws_close_code=4001)
        report = pr.compare_journey(JourneyType.WS_PTY)
        assert not report.is_passing

    def test_ws_message_type_divergence(self):
        """Verify WS message type sequence divergence is detected."""
        pr = ParityRunner()
        step = CHAT_JOURNEY_STEPS[1]  # chat_user_msg
        pr.local_runner.execute_step(
            step,
            ws_messages=[{'type': 'output'}, {'type': 'exit'}],
        )
        pr.sandbox_runner.execute_step(
            step,
            ws_messages=[{'type': 'output'}, {'type': 'error'}],
        )
        report = pr.compare_journey(JourneyType.WS_CHAT)
        assert not report.is_passing

    def test_error_category_divergence(self):
        """Verify error category divergence is detected."""
        pr = ParityRunner()
        step = FILE_JOURNEY_STEPS[0]
        pr.local_runner.execute_step(
            step,
            response_status=500,
            response_shape={'error': 'fail', 'category': 'internal'},
        )
        pr.sandbox_runner.execute_step(
            step,
            response_status=500,
            response_shape={'error': 'fail', 'category': 'provider'},
        )
        report = pr.compare_journey(JourneyType.HTTP_FILES)
        assert not report.is_passing


# ── Artifact integration ──


class TestArtifactIntegration:
    """Verify structured logging and timeline artifacts work with parity runner."""

    def test_logger_captures_all_steps(self):
        test_logger = StructuredTestLogger()
        runner = ScenarioRunner(logger=test_logger)
        for step in FILE_JOURNEY_STEPS:
            runner.execute_step(step, response_status=200)
        assert test_logger.count == len(FILE_JOURNEY_STEPS)

    def test_timeline_captures_all_steps(self):
        timeline = EventTimeline()
        runner = ScenarioRunner(timeline=timeline)
        for step in FILE_JOURNEY_STEPS:
            runner.execute_step(step, response_status=200)
        assert timeline.count == len(FILE_JOURNEY_STEPS)

    def test_request_id_unique_per_step(self):
        runner = ScenarioRunner()
        for step in FILE_JOURNEY_STEPS:
            runner.execute_step(step, response_status=200)
        request_ids = [r.request_id for r in runner.results]
        assert len(request_ids) == len(set(request_ids))

    def test_timeline_events_filterable_by_request_id(self):
        timeline = EventTimeline()
        runner = ScenarioRunner(timeline=timeline)
        result = runner.execute_step(FILE_JOURNEY_STEPS[0], response_status=200)
        runner.execute_step(FILE_JOURNEY_STEPS[1], response_status=200)
        filtered = timeline.filter_by_request_id(result.request_id)
        assert len(filtered) == 1

    def test_summary_json_serializable(self):
        pr = ParityRunner()
        for step in FILE_JOURNEY_STEPS[:2]:
            pr.local_runner.execute_step(step, response_status=200)
            pr.sandbox_runner.execute_step(step, response_status=200)
        pr.compare_journey(JourneyType.HTTP_FILES)
        serialized = json.dumps(pr.summary())
        parsed = json.loads(serialized)
        assert parsed['all_passing'] is True


# ── Enum coverage ──


class TestEnums:

    def test_journey_types(self):
        assert JourneyType.HTTP_FILES.value == 'http_files'
        assert JourneyType.HTTP_GIT.value == 'http_git'
        assert JourneyType.HTTP_SESSIONS.value == 'http_sessions'
        assert JourneyType.WS_PTY.value == 'ws_pty'
        assert JourneyType.WS_CHAT.value == 'ws_chat'
        assert JourneyType.TREE_TRAVERSAL.value == 'tree_traversal'

    def test_parity_verdicts(self):
        assert ParityVerdict.PASS.value == 'pass'
        assert ParityVerdict.FAIL.value == 'fail'
        assert ParityVerdict.WARN.value == 'warn'

    def test_step_outcomes(self):
        assert StepOutcome.SUCCESS.value == 'success'
        assert StepOutcome.ERROR.value == 'error'
        assert StepOutcome.SKIPPED.value == 'skipped'
