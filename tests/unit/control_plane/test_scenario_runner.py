"""Tests for the scenario parser and runner.

Bead: bd-223o.16.3 (K3)

Validates:
  - ScenarioParser: H1 extraction, step parsing, API signal table parsing,
    evidence bullets, failure mode tables, multi-scenario directory scanning
  - ScenarioRunner: step execution, status validation, key field checking,
    fail-fast behavior, error handling, variable substitution
  - ScenarioResult: summary generation, pass/fail aggregation
  - CLI variable parsing and scenario filtering
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from control_plane.app.testing.scenario_parser import (
    ApiSignal,
    FailureMode,
    ScenarioSpec,
    parse_scenario,
    parse_scenario_file,
    scan_scenario_dir,
)
from control_plane.app.testing.scenario_runner import (
    RunConfig,
    ScenarioResult,
    ScenarioRunner,
    StepOutcome,
    StepResult,
    _check_key_fields,
)


# ── Test fixtures ──────────────────────────────────────────────────


MINIMAL_SCENARIO = """\
# S-001: Login and Session Establishment

## Preconditions
- Control plane deployed and healthy.
- User registered.

## Steps
1. Browser navigates to control plane host.
2. App calls `GET /api/v1/app-config`.
3. User clicks login.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 2 | `GET /api/v1/app-config` | 200 | `app_id`, `name` |

### UI
- Login page shows app branding.

## Evidence Artifacts
- Screenshot: Login page with branding.
- API response: `/api/v1/app-config` JSON body.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Invalid token | 401 `auth_callback_failed` |
| Missing token | 400 `missing_token` |
"""

MULTI_SIGNAL_SCENARIO = """\
# S-002: Workspace Creation and Provisioning

## Preconditions
- User authenticated.

## Steps
1. User navigates to workspace list.
2. App calls `GET /api/v1/workspaces`.
3. User creates workspace.
4. App calls `POST /api/v1/workspaces`.
5. Workspace provisions.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 2 | `GET /api/v1/workspaces` | 200 | `workspaces[]` |
| 4 | `POST /api/v1/workspaces` | 202 | `workspace_id`, `status: provisioning` |

## Evidence Artifacts
- API response: workspace creation.

## Failure Modes
| Failure | Expected Behavior |
|---|---|
| Missing release | 503 `release_unavailable` |
"""


# =====================================================================
# 1. ScenarioParser — H1 extraction
# =====================================================================


class TestParserH1:

    def test_extracts_scenario_id(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        assert spec.scenario_id == 'S-001'

    def test_extracts_title(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        assert spec.title == 'Login and Session Establishment'

    def test_missing_h1_raises(self):
        with pytest.raises(ValueError, match='No scenario header'):
            parse_scenario('## No H1 here')

    def test_zero_padded_id(self):
        text = '# S-42: Short ID\n## Steps\n1. A step.'
        spec = parse_scenario(text)
        assert spec.scenario_id == 'S-042'

    def test_source_path_recorded(self):
        spec = parse_scenario(MINIMAL_SCENARIO, source_path='/test/s001.md')
        assert spec.source_path == '/test/s001.md'


# =====================================================================
# 2. ScenarioParser — Steps
# =====================================================================


class TestParserSteps:

    def test_extracts_numbered_steps(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        assert len(spec.steps) == 3
        assert spec.steps[0] == 'Browser navigates to control plane host.'

    def test_step_count_property(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        assert spec.step_count == 3

    def test_multi_signal_steps(self):
        spec = parse_scenario(MULTI_SIGNAL_SCENARIO)
        assert spec.step_count == 5


# =====================================================================
# 3. ScenarioParser — API signals
# =====================================================================


class TestParserApiSignals:

    def test_extracts_signal_from_table(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        assert len(spec.api_signals) == 1
        sig = spec.api_signals[0]
        assert sig.step == 2
        assert sig.method == 'GET'
        assert sig.path == '/api/v1/app-config'
        assert sig.status == 200
        assert 'app_id' in sig.key_fields

    def test_multi_signal_extraction(self):
        spec = parse_scenario(MULTI_SIGNAL_SCENARIO)
        assert len(spec.api_signals) == 2
        assert spec.api_signals[0].method == 'GET'
        assert spec.api_signals[1].method == 'POST'
        assert spec.api_signals[1].status == 202

    def test_api_step_numbers(self):
        spec = parse_scenario(MULTI_SIGNAL_SCENARIO)
        assert spec.api_step_numbers == (2, 4)

    def test_key_fields_with_value_assertion(self):
        spec = parse_scenario(MULTI_SIGNAL_SCENARIO)
        # POST signal has "status: provisioning" as key field.
        post_signal = spec.api_signals[1]
        assert 'status: provisioning' in post_signal.key_fields

    def test_signal_immutability(self):
        sig = ApiSignal(
            step=1, method='GET', path='/test',
            status=200, key_fields=('a',),
        )
        with pytest.raises(AttributeError):
            sig.step = 2


# =====================================================================
# 4. ScenarioParser — Preconditions and evidence
# =====================================================================


class TestParserSections:

    def test_extracts_preconditions(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        assert len(spec.preconditions) == 2
        assert 'Control plane deployed and healthy.' in spec.preconditions[0]

    def test_extracts_evidence_artifacts(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        assert len(spec.evidence_artifacts) == 2
        assert 'Screenshot' in spec.evidence_artifacts[0]

    def test_extracts_failure_modes(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        assert len(spec.failure_modes) == 2
        assert spec.failure_modes[0].failure == 'Invalid token'
        assert '401' in spec.failure_modes[0].expected_behavior

    def test_failure_mode_immutability(self):
        fm = FailureMode(failure='test', expected_behavior='400')
        with pytest.raises(AttributeError):
            fm.failure = 'changed'


# =====================================================================
# 5. ScenarioParser — File and directory scanning
# =====================================================================


class TestParserFileOps:

    def test_parse_file(self, tmp_path: Path):
        p = tmp_path / 's001_login.md'
        p.write_text(MINIMAL_SCENARIO)
        spec = parse_scenario_file(p)
        assert spec.scenario_id == 'S-001'
        assert str(p) in spec.source_path

    def test_parse_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            parse_scenario_file(tmp_path / 'missing.md')

    def test_scan_directory(self, tmp_path: Path):
        (tmp_path / 's001_login.md').write_text(MINIMAL_SCENARIO)
        (tmp_path / 's002_workspace.md').write_text(MULTI_SIGNAL_SCENARIO)
        (tmp_path / 'TEMPLATE.md').write_text('# Not a scenario')
        (tmp_path / 'README.md').write_text('# README')

        specs = scan_scenario_dir(tmp_path)
        assert len(specs) == 2
        assert specs[0].scenario_id == 'S-001'
        assert specs[1].scenario_id == 'S-002'

    def test_scan_empty_directory(self, tmp_path: Path):
        specs = scan_scenario_dir(tmp_path)
        assert specs == []

    def test_scan_sorted_by_name(self, tmp_path: Path):
        (tmp_path / 's003_third.md').write_text(
            '# S-003: Third\n## Steps\n1. Step.'
        )
        (tmp_path / 's001_first.md').write_text(MINIMAL_SCENARIO)
        specs = scan_scenario_dir(tmp_path)
        assert specs[0].scenario_id == 'S-001'
        assert specs[1].scenario_id == 'S-003'


# =====================================================================
# 6. ScenarioParser — Critical path detection
# =====================================================================


class TestParserCriticalPath:

    def test_default_is_critical(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        assert spec.critical_path is True

    def test_non_critical_detected(self):
        text = MINIMAL_SCENARIO.replace(
            '# S-001',
            '<!--\ncritical_path: false\n-->\n# S-001',
        )
        spec = parse_scenario(text)
        assert spec.critical_path is False


# =====================================================================
# 7. Key field checking
# =====================================================================


class TestKeyFieldChecking:

    def test_all_present(self):
        body = {'app_id': 'test', 'name': 'Test'}
        missing = _check_key_fields(body, ('app_id', 'name'))
        assert missing == []

    def test_missing_field(self):
        body = {'app_id': 'test'}
        missing = _check_key_fields(body, ('app_id', 'name'))
        assert 'name' in missing

    def test_none_body_all_missing(self):
        missing = _check_key_fields(None, ('app_id', 'name'))
        assert len(missing) == 2

    def test_empty_key_fields(self):
        missing = _check_key_fields({'a': 1}, ())
        assert missing == []

    def test_value_assertion_match(self):
        body = {'status': 'provisioning'}
        missing = _check_key_fields(body, ('status: provisioning',))
        assert missing == []

    def test_value_assertion_mismatch(self):
        body = {'status': 'ready'}
        missing = _check_key_fields(body, ('status: provisioning',))
        assert len(missing) == 1

    def test_array_field_notation(self):
        body = {'workspaces': [{'id': 1}]}
        missing = _check_key_fields(body, ('workspaces[]',))
        assert missing == []

    def test_array_field_missing(self):
        body = {'other': 'data'}
        missing = _check_key_fields(body, ('workspaces[]',))
        assert len(missing) == 1


# =====================================================================
# 8. StepResult properties
# =====================================================================


class TestStepResult:

    def test_passed_property(self):
        result = StepResult(
            step_number=1, method='GET', path='/test',
            expected_status=200, actual_status=200,
            outcome=StepOutcome.PASS,
            request_id='req-1', timestamp='2026-01-01T00:00:00',
            duration_ms=10.0,
        )
        assert result.passed is True

    def test_failed_property(self):
        result = StepResult(
            step_number=1, method='GET', path='/test',
            expected_status=200, actual_status=404,
            outcome=StepOutcome.FAIL,
            request_id='req-2', timestamp='2026-01-01T00:00:00',
            duration_ms=10.0,
        )
        assert result.passed is False

    def test_immutability(self):
        result = StepResult(
            step_number=1, method='GET', path='/test',
            expected_status=200, actual_status=200,
            outcome=StepOutcome.PASS,
            request_id='r', timestamp='t', duration_ms=1.0,
        )
        with pytest.raises(AttributeError):
            result.outcome = StepOutcome.FAIL


# =====================================================================
# 9. ScenarioResult properties
# =====================================================================


class TestScenarioResult:

    def _make_result(self, outcomes: list[StepOutcome]) -> ScenarioResult:
        steps = tuple(
            StepResult(
                step_number=i, method='GET', path='/test',
                expected_status=200, actual_status=200 if o == StepOutcome.PASS else 500,
                outcome=o, request_id=f'r-{i}',
                timestamp='2026-01-01T00:00:00', duration_ms=10.0,
            )
            for i, o in enumerate(outcomes, 1)
        )
        return ScenarioResult(
            scenario_id='S-001', title='Test',
            step_results=steps,
            started_at='2026-01-01T00:00:00',
            finished_at='2026-01-01T00:00:01',
            total_duration_ms=100.0,
        )

    def test_all_pass(self):
        result = self._make_result([StepOutcome.PASS, StepOutcome.PASS])
        assert result.passed is True
        assert result.pass_count == 2
        assert result.fail_count == 0

    def test_one_fail(self):
        result = self._make_result([StepOutcome.PASS, StepOutcome.FAIL])
        assert result.passed is False
        assert result.pass_count == 1
        assert result.fail_count == 1

    def test_error_count(self):
        result = self._make_result([StepOutcome.ERROR])
        assert result.error_count == 1
        assert result.passed is False

    def test_total_steps(self):
        result = self._make_result([StepOutcome.PASS] * 5)
        assert result.total_steps == 5

    def test_summary_dict(self):
        result = self._make_result([StepOutcome.PASS, StepOutcome.FAIL])
        summary = result.summary()
        assert summary['scenario_id'] == 'S-001'
        assert summary['passed'] is False
        assert summary['pass'] == 1
        assert summary['fail'] == 1
        assert 'duration_ms' in summary


# =====================================================================
# 10. ScenarioRunner — execution with mock server
# =====================================================================


class TestScenarioRunnerExecution:

    @pytest.fixture
    def spec(self) -> ScenarioSpec:
        return parse_scenario(MINIMAL_SCENARIO)

    @pytest.fixture
    def multi_spec(self) -> ScenarioSpec:
        return parse_scenario(MULTI_SIGNAL_SCENARIO)

    @pytest.mark.asyncio
    async def test_successful_step(self, spec: ScenarioSpec):
        """Mock a successful API response."""
        transport = httpx.MockTransport(lambda req: httpx.Response(
            200,
            json={'app_id': 'test', 'name': 'Test App'},
            headers={'x-request-id': 'req-abc'},
        ))
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test')
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(spec)
        assert result.passed is True
        assert result.total_steps == 1
        assert result.step_results[0].request_id == 'req-abc'

    @pytest.mark.asyncio
    async def test_status_mismatch_fails(self, spec: ScenarioSpec):
        """Wrong status code causes failure."""
        transport = httpx.MockTransport(lambda req: httpx.Response(
            500,
            json={'error': 'internal'},
        ))
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test')
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(spec)
        assert result.passed is False
        assert result.step_results[0].outcome == StepOutcome.FAIL
        assert 'Expected status 200' in (result.step_results[0].error_detail or '')

    @pytest.mark.asyncio
    async def test_missing_key_field_fails(self, spec: ScenarioSpec):
        """Missing key field causes failure."""
        transport = httpx.MockTransport(lambda req: httpx.Response(
            200,
            json={'app_id': 'test'},  # Missing 'name'.
        ))
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test')
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(spec)
        assert result.passed is False
        assert result.step_results[0].outcome == StepOutcome.FAIL
        assert 'name' in (result.step_results[0].error_detail or '')

    @pytest.mark.asyncio
    async def test_connection_error_produces_error_outcome(
        self, spec: ScenarioSpec,
    ):
        """HTTP connection error produces ERROR outcome."""
        def raise_error(req):
            raise httpx.ConnectError('Connection refused')

        transport = httpx.MockTransport(raise_error)
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test')
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(spec)
        assert result.step_results[0].outcome == StepOutcome.ERROR
        assert 'ConnectError' in (result.step_results[0].error_detail or '')

    @pytest.mark.asyncio
    async def test_fail_fast_skips_remaining(
        self, multi_spec: ScenarioSpec,
    ):
        """When fail_fast=True, remaining steps are skipped after failure."""
        call_count = 0

        def handler(req):
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, json={'error': 'fail'})

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test', fail_fast=True)
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(multi_spec)
        assert call_count == 1  # Only first step executed.
        assert result.total_steps == 2
        assert result.step_results[0].outcome == StepOutcome.FAIL
        assert result.step_results[1].outcome == StepOutcome.SKIP

    @pytest.mark.asyncio
    async def test_no_fail_fast_continues(
        self, multi_spec: ScenarioSpec,
    ):
        """When fail_fast=False, all steps execute even after failure."""
        call_count = 0

        def handler(req):
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, json={'error': 'fail'})

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test', fail_fast=False)
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(multi_spec)
        assert call_count == 2  # Both steps executed.
        assert result.step_results[0].outcome == StepOutcome.FAIL
        assert result.step_results[1].outcome == StepOutcome.FAIL


# =====================================================================
# 11. ScenarioRunner — variable substitution
# =====================================================================


class TestVariableSubstitution:

    @pytest.mark.asyncio
    async def test_path_variables_resolved(self):
        """URL path variables are resolved from variable_map."""
        text = """\
# S-004: File Edit

## Steps
1. Get files.

## Expected Signals

### API
| Step | Endpoint | Status | Key Fields |
|---|---|---|---|
| 1 | `GET /w/{workspace_id}/api/v1/files/` | 200 | `files` |
"""
        spec = parse_scenario(text)
        captured_urls: list[str] = []

        def handler(req):
            captured_urls.append(str(req.url))
            return httpx.Response(200, json={'files': []})

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(
            base_url='http://test',
            variable_map={'workspace_id': 'ws-abc'},
        )
        runner = ScenarioRunner(config, client=client)

        await runner.run(spec)
        assert 'ws-abc' in captured_urls[0]
        assert '{workspace_id}' not in captured_urls[0]


# =====================================================================
# 12. ScenarioRunner — response body capture
# =====================================================================


class TestResponseCapture:

    @pytest.mark.asyncio
    async def test_json_body_captured(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        body = {'app_id': 'test', 'name': 'App'}
        transport = httpx.MockTransport(lambda req: httpx.Response(
            200, json=body,
        ))
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test')
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(spec)
        assert result.step_results[0].response_body == body

    @pytest.mark.asyncio
    async def test_non_json_body_is_none(self):
        spec = parse_scenario(MINIMAL_SCENARIO)
        transport = httpx.MockTransport(lambda req: httpx.Response(
            200, text='not json',
        ))
        client = httpx.AsyncClient(transport=transport)
        config = RunConfig(base_url='http://test')
        runner = ScenarioRunner(config, client=client)

        result = await runner.run(spec)
        # Status is correct (200) but key fields missing since body is None.
        assert result.step_results[0].response_body is None


# =====================================================================
# 13. RunConfig
# =====================================================================


class TestRunConfig:

    def test_default_values(self):
        config = RunConfig(base_url='http://test')
        assert config.timeout_seconds == 30.0
        assert config.fail_fast is True
        assert config.session_cookie is None
        assert config.auth_token is None
        assert config.variable_map == {}

    def test_immutability(self):
        config = RunConfig(base_url='http://test')
        with pytest.raises(AttributeError):
            config.base_url = 'http://other'


# =====================================================================
# 14. Parse real scenario files
# =====================================================================


class TestParseRealScenarios:
    """Validate parser against actual test-scenarios/*.md files."""

    @pytest.fixture
    def scenarios_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent.parent / 'test-scenarios'

    def test_all_scenarios_parse(self, scenarios_dir: Path):
        """Every scenario file should parse without errors."""
        if not scenarios_dir.exists():
            pytest.skip('test-scenarios/ not found')

        specs = scan_scenario_dir(scenarios_dir)
        assert len(specs) >= 1

        for spec in specs:
            assert spec.scenario_id.startswith('S-')
            assert spec.title
            assert spec.step_count >= 1

    def test_s001_login_structure(self, scenarios_dir: Path):
        """S-001 has expected structure."""
        if not scenarios_dir.exists():
            pytest.skip('test-scenarios/ not found')

        path = scenarios_dir / 's001_login.md'
        if not path.exists():
            pytest.skip('s001_login.md not found')

        spec = parse_scenario_file(path)
        assert spec.scenario_id == 'S-001'
        assert len(spec.api_signals) >= 1
        assert len(spec.preconditions) >= 1
        assert len(spec.failure_modes) >= 1

    def test_s002_workspace_has_post_signal(self, scenarios_dir: Path):
        """S-002 has a POST signal for workspace creation."""
        if not scenarios_dir.exists():
            pytest.skip('test-scenarios/ not found')

        path = scenarios_dir / 's002_workspace_create.md'
        if not path.exists():
            pytest.skip('s002_workspace_create.md not found')

        spec = parse_scenario_file(path)
        post_signals = [s for s in spec.api_signals if s.method == 'POST']
        assert len(post_signals) >= 1
        assert post_signals[0].status == 202
