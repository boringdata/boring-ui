"""Tests for evidence store and beads comment formatting.

Bead: bd-223o.16.4.1 (K4a)

Tests cover:
  - AttachedScenario creation and serialization
  - EvidenceStore artifact attachment with result.json output
  - EvidenceStore per-step artifact grouping in result.json
  - EvidenceStore cross-scenario evidence index (index.json)
  - EvidenceStore directory isolation per scenario
  - format_beads_comment for passing and failing scenarios
  - format_beads_comment artifact links (screenshot, API, log)
  - format_beads_comment with evidence_base_url
  - Integration with ScenarioResult, StepResult, and EvidenceArtifact
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from control_plane.app.testing.evidence_store import (
    AttachedScenario,
    EvidenceStore,
    format_beads_comment,
)
from control_plane.app.testing.scenario_runner import (
    ScenarioResult,
    StepOutcome,
    StepResult,
)
from control_plane.app.testing.visual_proof import (
    ArtifactType,
    EvidenceArtifact,
)


# ── Fixtures ──────────────────────────────────────────────────────


def _make_step(
    *,
    step_number: int = 1,
    method: str = 'GET',
    path: str = '/api/v1/me',
    expected_status: int = 200,
    actual_status: int | None = 200,
    outcome: StepOutcome = StepOutcome.PASS,
    request_id: str = 'req-123',
    duration_ms: float = 42.5,
    response_body: dict | None = None,
    error_detail: str | None = None,
    missing_fields: tuple[str, ...] = (),
) -> StepResult:
    return StepResult(
        step_number=step_number,
        method=method,
        path=path,
        expected_status=expected_status,
        actual_status=actual_status,
        outcome=outcome,
        request_id=request_id,
        timestamp='2026-02-13T12:00:00+00:00',
        duration_ms=duration_ms,
        response_body=response_body,
        error_detail=error_detail,
        missing_fields=missing_fields,
    )


def _make_result(
    *,
    scenario_id: str = 'S-001',
    title: str = 'Login Flow',
    steps: tuple[StepResult, ...] | None = None,
) -> ScenarioResult:
    if steps is None:
        steps = (
            _make_step(step_number=1),
            _make_step(
                step_number=2,
                method='POST',
                path='/api/v1/workspaces',
                expected_status=202,
                actual_status=202,
                outcome=StepOutcome.PASS,
                duration_ms=150.0,
            ),
        )
    return ScenarioResult(
        scenario_id=scenario_id,
        title=title,
        step_results=steps,
        started_at='2026-02-13T12:00:00+00:00',
        finished_at='2026-02-13T12:00:01+00:00',
        total_duration_ms=1000.0,
    )


def _make_artifact(
    *,
    artifact_type: ArtifactType = ArtifactType.API_RESPONSE,
    step_number: int = 1,
    description: str = 'API response',
    file_path: str = 'S-001/step01_api.json',
    scenario_id: str = 'S-001',
) -> EvidenceArtifact:
    return EvidenceArtifact(
        artifact_type=artifact_type,
        step_number=step_number,
        description=description,
        file_path=file_path,
        timestamp='2026-02-13T12:00:00+00:00',
        scenario_id=scenario_id,
    )


# ── AttachedScenario ──────────────────────────────────────────────


class TestAttachedScenario:
    def test_to_dict(self):
        attached = AttachedScenario(
            scenario_id='S-001',
            title='Login Flow',
            passed=True,
            step_count=2,
            pass_count=2,
            fail_count=0,
            error_count=0,
            duration_ms=1000.0,
            started_at='2026-02-13T12:00:00+00:00',
            finished_at='2026-02-13T12:00:01+00:00',
            artifacts=({'type': 'api_response', 'step': 1},),
            output_path='S-001/result.json',
        )
        d = attached.to_dict()
        assert d['scenario_id'] == 'S-001'
        assert d['passed'] is True
        assert d['artifact_count'] == 1
        assert d['output_path'] == 'S-001/result.json'

    def test_frozen(self):
        attached = AttachedScenario(
            scenario_id='S-001', title='t', passed=True,
            step_count=0, pass_count=0, fail_count=0, error_count=0,
            duration_ms=0, started_at='', finished_at='',
            artifacts=(), output_path='',
        )
        with pytest.raises(AttributeError):
            attached.passed = False  # type: ignore[misc]


# ── EvidenceStore ─────────────────────────────────────────────────


class TestEvidenceStoreAttach:
    def test_attach_artifacts_writes_result_json(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')
        result = _make_result()
        artifacts = (
            _make_artifact(step_number=1, description='Me response'),
        )

        attached = store.attach_artifacts(result, artifacts)

        result_path = tmp_path / 'evidence' / 'S-001' / 'result.json'
        assert result_path.exists()

        content = json.loads(result_path.read_text())
        assert content['scenario_id'] == 'S-001'
        assert content['passed'] is True
        assert content['artifact_count'] == 1
        assert len(content['steps']) == 2
        assert content['steps'][0]['step'] == 1
        assert content['steps'][0]['method'] == 'GET'

    def test_attach_groups_artifacts_by_step(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')
        result = _make_result()
        artifacts = (
            _make_artifact(step_number=1, description='API 1'),
            _make_artifact(
                step_number=1,
                artifact_type=ArtifactType.SCREENSHOT,
                description='Screenshot 1',
                file_path='S-001/step01_screenshot.png',
            ),
            _make_artifact(step_number=2, description='API 2',
                           file_path='S-001/step02_api.json'),
        )

        store.attach_artifacts(result, artifacts)

        content = json.loads(
            (tmp_path / 'evidence' / 'S-001' / 'result.json').read_text()
        )
        # Step 1 should have 2 artifacts.
        step1 = content['steps'][0]
        assert len(step1['artifacts']) == 2

        # Step 2 should have 1 artifact.
        step2 = content['steps'][1]
        assert len(step2['artifacts']) == 1

    def test_attach_no_artifacts(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')
        result = _make_result()

        attached = store.attach_artifacts(result)

        content = json.loads(
            (tmp_path / 'evidence' / 'S-001' / 'result.json').read_text()
        )
        assert content['artifact_count'] == 0
        assert 'artifacts' not in content['steps'][0]

    def test_attach_returns_attached_scenario(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')
        result = _make_result()
        artifacts = (_make_artifact(),)

        attached = store.attach_artifacts(result, artifacts)
        assert attached.scenario_id == 'S-001'
        assert attached.passed is True
        assert attached.step_count == 2
        assert attached.pass_count == 2
        assert len(attached.artifacts) == 1
        assert attached.output_path == 'S-001/result.json'

    def test_attach_failed_scenario(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')
        result = _make_result(
            steps=(
                _make_step(step_number=1, outcome=StepOutcome.PASS),
                _make_step(
                    step_number=2, outcome=StepOutcome.FAIL,
                    actual_status=500, error_detail='Server error',
                ),
            ),
        )

        attached = store.attach_artifacts(result)
        assert attached.passed is False
        assert attached.fail_count == 1

        content = json.loads(
            (tmp_path / 'evidence' / 'S-001' / 'result.json').read_text()
        )
        assert content['passed'] is False
        assert content['steps'][1]['outcome'] == 'fail'
        assert content['steps'][1]['error'] == 'Server error'

    def test_attach_step_with_missing_fields(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')
        result = _make_result(
            steps=(
                _make_step(
                    step_number=1,
                    outcome=StepOutcome.FAIL,
                    missing_fields=('user_id', 'email'),
                    error_detail='Missing key fields: user_id, email',
                ),
            ),
        )

        store.attach_artifacts(result)

        content = json.loads(
            (tmp_path / 'evidence' / 'S-001' / 'result.json').read_text()
        )
        assert content['steps'][0]['missing_fields'] == ['user_id', 'email']


class TestEvidenceStoreIndex:
    def test_build_index_single_scenario(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')
        result = _make_result()
        store.attach_artifacts(result, (_make_artifact(),))

        index = store.build_index()

        assert index['scenario_count'] == 1
        assert index['overall_passed'] is True
        assert index['total_steps_pass'] == 2
        assert index['total_steps_fail'] == 0
        assert index['total_artifacts'] == 1

        # Index file should be written.
        index_path = tmp_path / 'evidence' / 'index.json'
        assert index_path.exists()
        saved = json.loads(index_path.read_text())
        assert saved['scenario_count'] == 1

    def test_build_index_multiple_scenarios(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')

        r1 = _make_result(scenario_id='S-001', title='Login')
        r2 = _make_result(scenario_id='S-002', title='Workspace')
        a1 = _make_artifact(scenario_id='S-001')
        a2 = _make_artifact(scenario_id='S-002', file_path='S-002/api.json')
        a3 = _make_artifact(
            scenario_id='S-002', file_path='S-002/screenshot.png',
            artifact_type=ArtifactType.SCREENSHOT,
        )

        store.attach_artifacts(r1, (a1,))
        store.attach_artifacts(r2, (a2, a3))

        index = store.build_index()
        assert index['scenario_count'] == 2
        assert index['total_artifacts'] == 3
        assert index['total_steps_pass'] == 4  # 2 per scenario.
        assert len(index['scenarios']) == 2

    def test_build_index_with_failure(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')

        r1 = _make_result(scenario_id='S-001')
        r2 = _make_result(
            scenario_id='S-002',
            steps=(
                _make_step(outcome=StepOutcome.FAIL, actual_status=500),
            ),
        )

        store.attach_artifacts(r1)
        store.attach_artifacts(r2)

        index = store.build_index()
        assert index['overall_passed'] is False
        assert index['total_steps_fail'] == 1

    def test_build_index_empty(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')
        index = store.build_index()
        assert index['scenario_count'] == 0
        assert index['overall_passed'] is True  # vacuously true
        assert index['total_artifacts'] == 0


class TestEvidenceStoreDirectories:
    def test_separate_directories_per_scenario(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')

        r1 = _make_result(scenario_id='S-001')
        r2 = _make_result(scenario_id='S-002')

        store.attach_artifacts(r1)
        store.attach_artifacts(r2)

        assert (tmp_path / 'evidence' / 'S-001' / 'result.json').exists()
        assert (tmp_path / 'evidence' / 'S-002' / 'result.json').exists()

    def test_output_dir_created_on_init(self, tmp_path: Path):
        out = tmp_path / 'deep' / 'nested' / 'evidence'
        store = EvidenceStore(out)
        assert out.exists()


# ── format_beads_comment ──────────────────────────────────────────


class TestFormatBeadsComment:
    def test_passing_scenario(self):
        result = _make_result()
        comment = format_beads_comment(result)

        assert '\u2714 S-001: Login Flow \u2014 PASSED' in comment
        assert '| 2 | 2 | 0 | 0 |' in comment
        assert 'Failed steps' not in comment

    def test_failing_scenario(self):
        result = _make_result(
            steps=(
                _make_step(step_number=1, outcome=StepOutcome.PASS),
                _make_step(
                    step_number=2,
                    method='POST',
                    path='/api/v1/workspaces',
                    outcome=StepOutcome.FAIL,
                    actual_status=500,
                    expected_status=202,
                    error_detail='Expected 202, got 500',
                ),
            ),
        )
        comment = format_beads_comment(result)

        assert '\u2718 S-001: Login Flow \u2014 FAILED' in comment
        assert '**Failed steps:**' in comment
        assert 'Step 2: POST /api/v1/workspaces' in comment
        assert 'Expected 202, got 500' in comment

    def test_with_error_step(self):
        result = _make_result(
            steps=(
                _make_step(
                    step_number=1,
                    outcome=StepOutcome.ERROR,
                    actual_status=None,
                    error_detail='ConnectError: refused',
                ),
            ),
        )
        comment = format_beads_comment(result)

        assert '**Failed steps:**' in comment
        assert 'ConnectError: refused' in comment

    def test_with_artifacts(self):
        result = _make_result()
        artifacts = (
            _make_artifact(
                artifact_type=ArtifactType.SCREENSHOT,
                description='Login page',
                file_path='S-001/step01_screenshot.png',
            ),
            _make_artifact(
                artifact_type=ArtifactType.API_RESPONSE,
                description='Me endpoint',
                file_path='S-001/step01_api.json',
            ),
            _make_artifact(
                artifact_type=ArtifactType.LOG_ENTRY,
                description='Auth log',
                file_path='S-001/step01_log.txt',
            ),
        )
        comment = format_beads_comment(result, artifacts)

        assert '**Evidence (3 artifacts):**' in comment
        assert '\U0001F4F8' in comment  # camera emoji for screenshot
        assert '\U0001F4CB' in comment  # clipboard emoji for API
        assert '\U0001F4DD' in comment  # memo emoji for log
        assert '[Login page](S-001/step01_screenshot.png)' in comment
        assert '[Me endpoint](S-001/step01_api.json)' in comment

    def test_with_base_url(self):
        result = _make_result()
        artifacts = (
            _make_artifact(file_path='S-001/step01_api.json'),
        )
        comment = format_beads_comment(
            result, artifacts,
            evidence_base_url='https://evidence.example.com/runs/42',
        )

        assert 'https://evidence.example.com/runs/42/S-001/step01_api.json' in comment

    def test_no_artifacts(self):
        result = _make_result()
        comment = format_beads_comment(result)

        assert 'Evidence' not in comment

    def test_run_timestamps(self):
        result = _make_result()
        comment = format_beads_comment(result)

        assert '2026-02-13T12:00:00+00:00' in comment
        assert '2026-02-13T12:00:01+00:00' in comment


# ── Integration ───────────────────────────────────────────────────


class TestIntegration:
    def test_full_workflow(self, tmp_path: Path):
        """Attach artifacts, build index, generate beads comment."""
        store = EvidenceStore(tmp_path / 'evidence')

        # Two scenarios, one passes, one fails.
        r1 = _make_result(scenario_id='S-001', title='Login')
        r2 = _make_result(
            scenario_id='S-002',
            title='Workspace',
            steps=(
                _make_step(step_number=1, outcome=StepOutcome.PASS),
                _make_step(
                    step_number=2, outcome=StepOutcome.FAIL,
                    actual_status=503,
                    error_detail='Service unavailable',
                ),
            ),
        )

        a1 = (_make_artifact(scenario_id='S-001'),)
        a2 = (
            _make_artifact(scenario_id='S-002', file_path='S-002/api.json'),
            _make_artifact(
                scenario_id='S-002', file_path='S-002/screenshot.png',
                artifact_type=ArtifactType.SCREENSHOT,
                description='Error state',
            ),
        )

        store.attach_artifacts(r1, a1)
        store.attach_artifacts(r2, a2)

        # Build index.
        index = store.build_index()
        assert index['overall_passed'] is False
        assert index['scenario_count'] == 2
        assert index['total_artifacts'] == 3

        # Generate beads comments.
        c1 = format_beads_comment(r1, a1)
        assert 'PASSED' in c1

        c2 = format_beads_comment(r2, a2)
        assert 'FAILED' in c2
        assert 'Service unavailable' in c2
        assert 'Error state' in c2

    def test_index_scenarios_match_attached(self, tmp_path: Path):
        store = EvidenceStore(tmp_path / 'evidence')

        for i in range(3):
            r = _make_result(scenario_id=f'S-{i+1:03d}', title=f'Scenario {i+1}')
            store.attach_artifacts(r)

        index = store.build_index()
        assert len(index['scenarios']) == 3
        ids = [s['scenario_id'] for s in index['scenarios']]
        assert ids == ['S-001', 'S-002', 'S-003']
