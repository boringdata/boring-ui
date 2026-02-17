"""Structured pass/fail logs and per-step evidence capture.

Bead: bd-223o.16.3.1 (K3a)

Validates the machine-readable run output format that ties each
scenario step to expected and observed behavior:

  1. StepResult.to_dict() — per-step expected vs observed serialization.
  2. ScenarioResult.to_run_log() — full scenario with per-step detail.
  3. RunLog — multi-scenario aggregation with metadata and verdict.
  4. RunLog.to_json() — JSON serialization round-trip.
  5. RunLog.write() — file persistence.
  6. RunLog.failed_steps() — cross-scenario failure extraction.
  7. Evidence traceability — request IDs, timestamps, error details.
  8. Integration with runner — end-to-end structured output from run.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from control_plane.app.testing.run_log import RunLog
from control_plane.app.testing.scenario_parser import parse_scenario
from control_plane.app.testing.scenario_runner import (
    RunConfig,
    ScenarioResult,
    ScenarioRunner,
    StepOutcome,
    StepResult,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _step(
    *,
    step_number: int = 1,
    method: str = 'GET',
    path: str = '/test',
    expected: int = 200,
    actual: int | None = 200,
    outcome: StepOutcome = StepOutcome.PASS,
    request_id: str = 'req-001',
    timestamp: str = '2026-01-01T00:00:00+00:00',
    duration_ms: float = 12.5,
    response_body: dict | None = None,
    error_detail: str | None = None,
    missing_fields: tuple[str, ...] = (),
) -> StepResult:
    return StepResult(
        step_number=step_number,
        method=method,
        path=path,
        expected_status=expected,
        actual_status=actual,
        outcome=outcome,
        request_id=request_id,
        timestamp=timestamp,
        duration_ms=duration_ms,
        response_body=response_body,
        error_detail=error_detail,
        missing_fields=missing_fields,
    )


def _scenario(
    *,
    scenario_id: str = 'S-001',
    title: str = 'Test Scenario',
    steps: tuple[StepResult, ...] | None = None,
) -> ScenarioResult:
    if steps is None:
        steps = (_step(),)
    return ScenarioResult(
        scenario_id=scenario_id,
        title=title,
        step_results=steps,
        started_at='2026-01-01T00:00:00+00:00',
        finished_at='2026-01-01T00:00:01+00:00',
        total_duration_ms=100.0,
    )


MINIMAL_SCENARIO_MD = """\
# S-010: Structured Log Test

## Steps
1. Fetch app config.
2. Fetch workspaces.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 1 | `GET /api/v1/app-config` | 200 | `app_id`, `name` |
| 2 | `GET /api/v1/workspaces` | 200 | `workspaces[]` |
"""


# =====================================================================
# 1. StepResult.to_dict — per-step expected vs observed
# =====================================================================


class TestStepResultToDict:

    def test_pass_step_has_expected_and_observed(self):
        step = _step(expected=200, actual=200)
        d = step.to_dict()
        assert d['expected']['status'] == 200
        assert d['observed']['status'] == 200
        assert d['outcome'] == 'pass'

    def test_fail_step_captures_mismatch(self):
        step = _step(
            expected=200, actual=404,
            outcome=StepOutcome.FAIL,
            error_detail='Expected status 200, got 404',
        )
        d = step.to_dict()
        assert d['expected']['status'] == 200
        assert d['observed']['status'] == 404
        assert d['outcome'] == 'fail'
        assert d['error_detail'] == 'Expected status 200, got 404'

    def test_error_step_captures_detail(self):
        step = _step(
            actual=None,
            outcome=StepOutcome.ERROR,
            error_detail='ConnectError: Connection refused',
        )
        d = step.to_dict()
        assert d['observed']['status'] is None
        assert d['outcome'] == 'error'
        assert 'ConnectError' in d['error_detail']

    def test_skip_step_serialized(self):
        step = _step(
            actual=None,
            outcome=StepOutcome.SKIP,
            error_detail='Skipped due to prior failure',
        )
        d = step.to_dict()
        assert d['outcome'] == 'skip'

    def test_includes_request_id_and_timestamp(self):
        step = _step(request_id='req-xyz', timestamp='2026-01-01T12:00:00Z')
        d = step.to_dict()
        assert d['request_id'] == 'req-xyz'
        assert d['timestamp'] == '2026-01-01T12:00:00Z'

    def test_includes_duration(self):
        step = _step(duration_ms=42.567)
        d = step.to_dict()
        assert d['duration_ms'] == 42.57

    def test_includes_method_and_path(self):
        step = _step(method='POST', path='/api/v1/workspaces')
        d = step.to_dict()
        assert d['method'] == 'POST'
        assert d['path'] == '/api/v1/workspaces'

    def test_missing_fields_captured(self):
        step = _step(
            outcome=StepOutcome.FAIL,
            missing_fields=('app_id', 'name'),
            error_detail='Missing key fields: app_id, name',
        )
        d = step.to_dict()
        assert d['expected']['key_fields'] == ['app_id', 'name']
        assert d['observed']['missing_fields'] == ['app_id', 'name']

    def test_body_excluded_by_default(self):
        step = _step(response_body={'app_id': 'test'})
        d = step.to_dict()
        assert 'body' not in d.get('observed', {})

    def test_body_included_when_requested(self):
        body = {'app_id': 'test', 'name': 'App'}
        step = _step(response_body=body)
        d = step.to_dict(include_body=True)
        assert d['observed']['body'] == body

    def test_no_body_when_none(self):
        step = _step(response_body=None)
        d = step.to_dict(include_body=True)
        assert 'body' not in d.get('observed', {})

    def test_to_dict_is_json_serializable(self):
        step = _step(response_body={'key': 'value'})
        d = step.to_dict(include_body=True)
        json_str = json.dumps(d)
        assert json.loads(json_str) == d


# =====================================================================
# 2. ScenarioResult.to_run_log — full scenario with per-step detail
# =====================================================================


class TestScenarioResultToRunLog:

    def test_contains_scenario_metadata(self):
        result = _scenario(scenario_id='S-001', title='Login')
        log = result.to_run_log()
        assert log['scenario_id'] == 'S-001'
        assert log['title'] == 'Login'
        assert log['started_at']
        assert log['finished_at']

    def test_verdict_pass(self):
        result = _scenario(steps=(
            _step(outcome=StepOutcome.PASS),
            _step(step_number=2, outcome=StepOutcome.PASS),
        ))
        log = result.to_run_log()
        assert log['verdict'] == 'pass'

    def test_verdict_fail(self):
        result = _scenario(steps=(
            _step(outcome=StepOutcome.PASS),
            _step(step_number=2, outcome=StepOutcome.FAIL, actual=500),
        ))
        log = result.to_run_log()
        assert log['verdict'] == 'fail'

    def test_counts_correct(self):
        result = _scenario(steps=(
            _step(step_number=1, outcome=StepOutcome.PASS),
            _step(step_number=2, outcome=StepOutcome.FAIL, actual=500),
            _step(step_number=3, outcome=StepOutcome.SKIP, actual=None),
            _step(step_number=4, outcome=StepOutcome.ERROR, actual=None),
        ))
        log = result.to_run_log()
        assert log['counts']['total'] == 4
        assert log['counts']['pass'] == 1
        assert log['counts']['fail'] == 1
        assert log['counts']['skip'] == 1
        assert log['counts']['error'] == 1

    def test_steps_are_per_step_dicts(self):
        result = _scenario(steps=(
            _step(step_number=1, method='GET', path='/a'),
            _step(step_number=2, method='POST', path='/b'),
        ))
        log = result.to_run_log()
        assert len(log['steps']) == 2
        assert log['steps'][0]['step'] == 1
        assert log['steps'][0]['method'] == 'GET'
        assert log['steps'][1]['step'] == 2
        assert log['steps'][1]['method'] == 'POST'

    def test_steps_have_expected_and_observed(self):
        result = _scenario(steps=(
            _step(expected=200, actual=200),
        ))
        log = result.to_run_log()
        step = log['steps'][0]
        assert 'expected' in step
        assert 'observed' in step
        assert step['expected']['status'] == 200
        assert step['observed']['status'] == 200

    def test_include_bodies_propagated(self):
        body = {'app_id': 'test'}
        result = _scenario(steps=(
            _step(response_body=body),
        ))
        log = result.to_run_log(include_bodies=True)
        assert log['steps'][0]['observed']['body'] == body

    def test_to_run_log_is_json_serializable(self):
        result = _scenario()
        log = result.to_run_log()
        json_str = json.dumps(log)
        assert json.loads(json_str) == log

    def test_duration_included(self):
        result = _scenario()
        log = result.to_run_log()
        assert 'duration_ms' in log
        assert log['duration_ms'] == 100.0


# =====================================================================
# 3. RunLog — multi-scenario aggregation
# =====================================================================


class TestRunLog:

    def test_from_results_generates_run_id(self):
        result = _scenario()
        log = RunLog.from_results([result])
        assert log.run_id.startswith('run-')
        assert len(log.run_id) > 5

    def test_from_results_custom_run_id(self):
        result = _scenario()
        log = RunLog.from_results([result], run_id='run-custom')
        assert log.run_id == 'run-custom'

    def test_overall_passed_all_pass(self):
        results = [
            _scenario(scenario_id='S-001'),
            _scenario(scenario_id='S-002'),
        ]
        log = RunLog.from_results(results)
        assert log.overall_passed is True

    def test_overall_passed_with_failure(self):
        results = [
            _scenario(scenario_id='S-001'),
            _scenario(
                scenario_id='S-002',
                steps=(_step(outcome=StepOutcome.FAIL, actual=500),),
            ),
        ]
        log = RunLog.from_results(results)
        assert log.overall_passed is False

    def test_scenario_count(self):
        results = [_scenario(scenario_id=f'S-{i:03d}') for i in range(3)]
        log = RunLog.from_results(results)
        assert log.scenario_count == 3

    def test_total_steps_across_scenarios(self):
        results = [
            _scenario(
                scenario_id='S-001',
                steps=(_step(step_number=1), _step(step_number=2)),
            ),
            _scenario(
                scenario_id='S-002',
                steps=(_step(step_number=1),),
            ),
        ]
        log = RunLog.from_results(results)
        assert log.total_steps == 3

    def test_total_pass_fail_error(self):
        results = [
            _scenario(steps=(
                _step(step_number=1, outcome=StepOutcome.PASS),
                _step(step_number=2, outcome=StepOutcome.FAIL, actual=500),
            )),
            _scenario(
                scenario_id='S-002',
                steps=(
                    _step(step_number=1, outcome=StepOutcome.ERROR, actual=None),
                ),
            ),
        ]
        log = RunLog.from_results(results)
        assert log.total_pass == 1
        assert log.total_fail == 1
        assert log.total_error == 1

    def test_metadata_included(self):
        log = RunLog.from_results(
            [_scenario()],
            metadata={'base_url': 'http://localhost:8000', 'auth': 'token'},
        )
        assert log.metadata['base_url'] == 'http://localhost:8000'

    def test_empty_results(self):
        log = RunLog.from_results([])
        assert log.overall_passed is True
        assert log.scenario_count == 0
        assert log.total_steps == 0


# =====================================================================
# 4. RunLog.to_json — JSON serialization round-trip
# =====================================================================


class TestRunLogSerialization:

    def test_to_dict_structure(self):
        result = _scenario()
        log = RunLog.from_results([result], run_id='run-test')
        d = log.to_dict()
        assert d['run_id'] == 'run-test'
        assert 'created_at' in d
        assert 'overall_passed' in d
        assert 'summary' in d
        assert 'scenarios' in d
        assert 'metadata' in d

    def test_summary_counts(self):
        results = [
            _scenario(steps=(
                _step(outcome=StepOutcome.PASS),
                _step(step_number=2, outcome=StepOutcome.FAIL, actual=500),
            )),
        ]
        log = RunLog.from_results(results, run_id='run-test')
        summary = log.to_dict()['summary']
        assert summary['scenarios'] == 1
        assert summary['steps'] == 2
        assert summary['pass'] == 1
        assert summary['fail'] == 1

    def test_to_json_valid(self):
        result = _scenario()
        log = RunLog.from_results([result], run_id='run-test')
        json_str = log.to_json()
        parsed = json.loads(json_str)
        assert parsed['run_id'] == 'run-test'

    def test_to_json_round_trip(self):
        results = [
            _scenario(steps=(
                _step(step_number=1, response_body={'app_id': 'test'}),
            )),
        ]
        log = RunLog.from_results(
            results, run_id='run-rt',
            include_bodies=True,
            metadata={'env': 'test'},
        )
        json_str = log.to_json()
        parsed = json.loads(json_str)
        assert parsed['run_id'] == 'run-rt'
        assert parsed['metadata']['env'] == 'test'
        assert parsed['scenarios'][0]['steps'][0]['observed']['body'] == {'app_id': 'test'}

    def test_to_json_indent(self):
        log = RunLog.from_results([_scenario()], run_id='run-i')
        compact = log.to_json(indent=0)
        pretty = log.to_json(indent=4)
        assert len(pretty) > len(compact)


# =====================================================================
# 5. RunLog.write — file persistence
# =====================================================================


class TestRunLogWrite:

    def test_write_creates_file(self, tmp_path: Path):
        log = RunLog.from_results([_scenario()], run_id='run-write')
        output = tmp_path / 'evidence' / 'run-write.json'
        log.write(output)

        assert output.exists()
        parsed = json.loads(output.read_text())
        assert parsed['run_id'] == 'run-write'

    def test_write_creates_parent_dirs(self, tmp_path: Path):
        output = tmp_path / 'deep' / 'nested' / 'run.json'
        log = RunLog.from_results([_scenario()], run_id='run-nested')
        log.write(output)
        assert output.exists()

    def test_written_file_matches_to_json(self, tmp_path: Path):
        log = RunLog.from_results([_scenario()], run_id='run-match')
        output = tmp_path / 'run.json'
        log.write(output)
        assert output.read_text() == log.to_json()


# =====================================================================
# 6. RunLog.failed_steps — cross-scenario failure extraction
# =====================================================================


class TestRunLogFailedSteps:

    def test_no_failures(self):
        log = RunLog.from_results([_scenario()])
        assert log.failed_steps() == []

    def test_extracts_failed_steps_with_scenario_id(self):
        results = [
            _scenario(
                scenario_id='S-001',
                steps=(
                    _step(step_number=1, outcome=StepOutcome.PASS),
                    _step(
                        step_number=2, outcome=StepOutcome.FAIL,
                        actual=500, error_detail='Expected 200, got 500',
                    ),
                ),
            ),
        ]
        log = RunLog.from_results(results)
        failures = log.failed_steps()
        assert len(failures) == 1
        assert failures[0]['scenario_id'] == 'S-001'
        assert failures[0]['step'] == 2
        assert failures[0]['outcome'] == 'fail'

    def test_extracts_errors_too(self):
        results = [
            _scenario(steps=(
                _step(
                    outcome=StepOutcome.ERROR, actual=None,
                    error_detail='ConnectError',
                ),
            )),
        ]
        log = RunLog.from_results(results)
        failures = log.failed_steps()
        assert len(failures) == 1
        assert failures[0]['outcome'] == 'error'

    def test_cross_scenario_failures(self):
        results = [
            _scenario(
                scenario_id='S-001',
                steps=(_step(step_number=1, outcome=StepOutcome.FAIL, actual=404),),
            ),
            _scenario(
                scenario_id='S-002',
                steps=(
                    _step(step_number=1, outcome=StepOutcome.PASS),
                    _step(step_number=2, outcome=StepOutcome.ERROR, actual=None),
                ),
            ),
        ]
        log = RunLog.from_results(results)
        failures = log.failed_steps()
        assert len(failures) == 2
        assert failures[0]['scenario_id'] == 'S-001'
        assert failures[1]['scenario_id'] == 'S-002'

    def test_skipped_steps_not_counted_as_failures(self):
        results = [
            _scenario(steps=(
                _step(outcome=StepOutcome.SKIP, actual=None),
            )),
        ]
        log = RunLog.from_results(results)
        assert log.failed_steps() == []


# =====================================================================
# 7. Evidence traceability — request IDs, timestamps, error details
# =====================================================================


class TestEvidenceTraceability:

    def test_request_id_preserved_in_run_log(self):
        result = _scenario(steps=(
            _step(request_id='req-abc-123'),
        ))
        log = result.to_run_log()
        assert log['steps'][0]['request_id'] == 'req-abc-123'

    def test_timestamp_preserved_in_run_log(self):
        ts = '2026-02-13T10:30:00+00:00'
        result = _scenario(steps=(_step(timestamp=ts),))
        log = result.to_run_log()
        assert log['steps'][0]['timestamp'] == ts

    def test_error_detail_preserved(self):
        result = _scenario(steps=(
            _step(
                outcome=StepOutcome.FAIL, actual=401,
                error_detail='Expected status 200, got 401',
            ),
        ))
        log = result.to_run_log()
        assert log['steps'][0]['error_detail'] == 'Expected status 200, got 401'

    def test_missing_fields_traceable(self):
        result = _scenario(steps=(
            _step(
                outcome=StepOutcome.FAIL,
                missing_fields=('workspace_id', 'status'),
                error_detail='Missing key fields: workspace_id, status',
            ),
        ))
        log = result.to_run_log()
        step = log['steps'][0]
        assert step['expected']['key_fields'] == ['workspace_id', 'status']
        assert step['observed']['missing_fields'] == ['workspace_id', 'status']

    def test_full_run_log_traceable_to_scenario(self):
        """Every step in RunLog can be traced to its parent scenario."""
        results = [
            _scenario(scenario_id='S-001', steps=(
                _step(step_number=1, request_id='r1'),
                _step(step_number=2, request_id='r2'),
            )),
            _scenario(scenario_id='S-002', steps=(
                _step(step_number=1, request_id='r3'),
            )),
        ]
        log = RunLog.from_results(results, run_id='run-trace')
        d = log.to_dict()

        # Each scenario's steps carry request IDs.
        s1_steps = d['scenarios'][0]['steps']
        s2_steps = d['scenarios'][1]['steps']
        assert s1_steps[0]['request_id'] == 'r1'
        assert s1_steps[1]['request_id'] == 'r2'
        assert s2_steps[0]['request_id'] == 'r3'

        # Scenario ID is at the scenario level.
        assert d['scenarios'][0]['scenario_id'] == 'S-001'
        assert d['scenarios'][1]['scenario_id'] == 'S-002'


# =====================================================================
# 8. Integration with runner — end-to-end structured output
# =====================================================================


class TestRunnerIntegration:

    @pytest.mark.asyncio
    async def test_run_produces_structured_log(self):
        """Full runner execution produces valid run log output."""
        spec = parse_scenario(MINIMAL_SCENARIO_MD)

        call_count = 0
        responses = [
            httpx.Response(200, json={'app_id': 'test', 'name': 'App'},
                           headers={'x-request-id': 'req-001'}),
            httpx.Response(200, json={'workspaces': [{'id': 'ws-1'}]},
                           headers={'x-request-id': 'req-002'}),
        ]

        def handler(req):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test')
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(spec)
        log = result.to_run_log()

        assert log['verdict'] == 'pass'
        assert log['counts']['total'] == 2
        assert log['counts']['pass'] == 2
        assert len(log['steps']) == 2
        assert log['steps'][0]['request_id'] == 'req-001'
        assert log['steps'][1]['request_id'] == 'req-002'

    @pytest.mark.asyncio
    async def test_run_log_from_multiple_scenarios(self):
        """RunLog aggregates multiple scenario runs."""
        spec1 = parse_scenario(MINIMAL_SCENARIO_MD)
        spec2 = parse_scenario("""\
# S-020: Health Check

## Steps
1. Check health.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 1 | `GET /health` | 200 | `status` |
""")

        def ok_handler(req):
            return httpx.Response(
                200,
                json={'app_id': 'a', 'name': 'N', 'workspaces': [], 'status': 'ok'},
                headers={'x-request-id': 'req-auto'},
            )

        transport = httpx.MockTransport(ok_handler)
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test')
        runner = ScenarioRunner(config, client=client)

        r1 = await runner.run(spec1)
        r2 = await runner.run(spec2)

        run_log = RunLog.from_results(
            [r1, r2],
            run_id='run-multi',
            metadata={'base_url': 'http://test'},
        )

        assert run_log.overall_passed is True
        assert run_log.scenario_count == 2
        assert run_log.total_steps == 3

        d = run_log.to_dict()
        assert d['summary']['scenarios'] == 2
        assert d['summary']['steps'] == 3
        assert d['metadata']['base_url'] == 'http://test'

    @pytest.mark.asyncio
    async def test_run_log_captures_failure_detail(self):
        """RunLog captures failure details from runner execution."""
        spec = parse_scenario(MINIMAL_SCENARIO_MD)

        def fail_handler(req):
            return httpx.Response(500, json={'error': 'internal'})

        transport = httpx.MockTransport(fail_handler)
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test', fail_fast=False)
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(spec)
        log = RunLog.from_results([result], run_id='run-fail')

        assert log.overall_passed is False
        failures = log.failed_steps()
        assert len(failures) == 2

        for f in failures:
            assert f['scenario_id'] == 'S-010'
            assert f['outcome'] == 'fail'
            assert f['observed']['status'] == 500
            assert f['expected']['status'] == 200

    @pytest.mark.asyncio
    async def test_run_log_json_round_trip_from_runner(self):
        """JSON output from runner can be parsed back."""
        spec = parse_scenario(MINIMAL_SCENARIO_MD)

        def handler(req):
            return httpx.Response(
                200, json={'app_id': 'a', 'name': 'N', 'workspaces': []},
                headers={'x-request-id': 'req-rt'},
            )

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        runner = ScenarioRunner(RunConfig(base_url='http://test'), client=client)

        result = await runner.run(spec)
        log = RunLog.from_results([result], run_id='run-json-rt')

        json_str = log.to_json()
        parsed = json.loads(json_str)

        assert parsed['run_id'] == 'run-json-rt'
        assert parsed['overall_passed'] is True
        assert len(parsed['scenarios']) == 1
        assert len(parsed['scenarios'][0]['steps']) == 2

    @pytest.mark.asyncio
    async def test_run_log_write_from_runner(self, tmp_path: Path):
        """RunLog.write produces a valid file from real runner output."""
        spec = parse_scenario(MINIMAL_SCENARIO_MD)

        def handler(req):
            return httpx.Response(
                200, json={'app_id': 'a', 'name': 'N', 'workspaces': []},
            )

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        runner = ScenarioRunner(RunConfig(base_url='http://test'), client=client)

        result = await runner.run(spec)
        log = RunLog.from_results([result], run_id='run-file')

        output = tmp_path / 'evidence' / 'run-file.json'
        log.write(output)

        assert output.exists()
        parsed = json.loads(output.read_text())
        assert parsed['run_id'] == 'run-file'
        assert parsed['overall_passed'] is True
