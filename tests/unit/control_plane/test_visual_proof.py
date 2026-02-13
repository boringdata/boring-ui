"""Tests for visual proof capture and report generation.

Bead: bd-223o.16.4 (K4)

Tests cover:
  - EvidenceArtifact creation and serialization
  - CaptureConfig defaults
  - ProofSession API response recording
  - ProofSession log entry recording
  - ProofSession finalization and manifest writing
  - ProofSession screenshot capture (with mocked browser)
  - BrowserCapture subprocess invocation (mocked)
  - ProofReportBuilder section assembly
  - build_proof_report convenience function
  - Artifact-to-Markdown formatting
  - Integration with ScenarioResult/StepResult
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from control_plane.app.testing.visual_proof import (
    ArtifactType,
    BrowserCapture,
    CaptureConfig,
    EvidenceArtifact,
    ProofSession,
    _escape_js,
    _safe_path,
)
from control_plane.app.testing.proof_report import (
    ProofReportBuilder,
    build_proof_report,
    _format_artifact,
)
from control_plane.app.testing.scenario_runner import (
    ScenarioResult,
    StepOutcome,
    StepResult,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Temporary output directory for evidence artifacts."""
    return tmp_path / 'evidence'


@pytest.fixture
def capture_config(tmp_output: Path) -> CaptureConfig:
    return CaptureConfig(output_dir=tmp_output)


@pytest.fixture
def proof_session(capture_config: CaptureConfig) -> ProofSession:
    return ProofSession(capture_config, 'S-001')


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
            _make_step(step_number=1, outcome=StepOutcome.PASS),
            _make_step(step_number=2, method='POST', path='/api/v1/workspaces',
                       expected_status=202, actual_status=202,
                       outcome=StepOutcome.PASS, duration_ms=150.0),
        )
    return ScenarioResult(
        scenario_id=scenario_id,
        title=title,
        step_results=steps,
        started_at='2026-02-13T12:00:00+00:00',
        finished_at='2026-02-13T12:00:01+00:00',
        total_duration_ms=1000.0,
    )


# ── EvidenceArtifact ──────────────────────────────────────────────


class TestEvidenceArtifact:
    def test_create_screenshot_artifact(self):
        a = EvidenceArtifact(
            artifact_type=ArtifactType.SCREENSHOT,
            step_number=1,
            description='Login page',
            file_path='S-001/step01_screenshot.png',
            timestamp='2026-02-13T12:00:00+00:00',
            scenario_id='S-001',
        )
        assert a.artifact_type == ArtifactType.SCREENSHOT
        assert a.step_number == 1
        assert a.scenario_id == 'S-001'
        assert a.metadata == {}

    def test_create_api_response_artifact(self):
        a = EvidenceArtifact(
            artifact_type=ArtifactType.API_RESPONSE,
            step_number=2,
            description='GET /api/v1/me -> 200',
            file_path='S-001/step02_api_get_me.json',
            timestamp='2026-02-13T12:00:00+00:00',
            scenario_id='S-001',
            metadata={'status': 200},
        )
        assert a.artifact_type == ArtifactType.API_RESPONSE
        assert a.metadata == {'status': 200}

    def test_to_dict(self):
        a = EvidenceArtifact(
            artifact_type=ArtifactType.HAR,
            step_number=3,
            description='HAR capture',
            file_path='S-001/step03_har.json',
            timestamp='2026-02-13T12:00:00+00:00',
            scenario_id='S-001',
            metadata={'size_bytes': 1024},
        )
        d = a.to_dict()
        assert d['type'] == 'har'
        assert d['step'] == 3
        assert d['file'] == 'S-001/step03_har.json'
        assert d['metadata']['size_bytes'] == 1024

    def test_frozen(self):
        a = EvidenceArtifact(
            artifact_type=ArtifactType.LOG_ENTRY,
            step_number=1,
            description='test',
            file_path='test.txt',
            timestamp='2026-02-13T12:00:00+00:00',
            scenario_id='S-001',
        )
        with pytest.raises(AttributeError):
            a.step_number = 2  # type: ignore[misc]

    def test_artifact_type_enum_values(self):
        assert ArtifactType.SCREENSHOT.value == 'screenshot'
        assert ArtifactType.HAR.value == 'har'
        assert ArtifactType.API_RESPONSE.value == 'api_response'
        assert ArtifactType.LOG_ENTRY.value == 'log_entry'


# ── CaptureConfig ─────────────────────────────────────────────────


class TestCaptureConfig:
    def test_defaults(self, tmp_output: Path):
        config = CaptureConfig(output_dir=tmp_output)
        assert config.viewport_width == 1280
        assert config.viewport_height == 720
        assert config.screenshot_format == 'png'
        assert config.full_page is False
        assert config.timeout_ms == 15000

    def test_custom_values(self, tmp_output: Path):
        config = CaptureConfig(
            output_dir=tmp_output,
            viewport_width=1920,
            viewport_height=1080,
            screenshot_format='jpeg',
            full_page=True,
            timeout_ms=30000,
        )
        assert config.viewport_width == 1920
        assert config.full_page is True
        assert config.screenshot_format == 'jpeg'


# ── ProofSession ──────────────────────────────────────────────────


class TestProofSessionApiResponse:
    def test_record_api_response_creates_file(self, proof_session: ProofSession):
        artifact = proof_session.record_api_response(
            step=2,
            method='GET',
            path='/api/v1/me',
            status=200,
            body={'user_id': 'u1', 'email': 'test@example.com'},
            request_id='req-abc',
        )
        assert artifact.artifact_type == ArtifactType.API_RESPONSE
        assert artifact.step_number == 2

        # File should exist.
        full_path = proof_session.scenario_dir / 'step02_api_get_api_v1_me.json'
        assert full_path.exists()

        content = json.loads(full_path.read_text())
        assert content['method'] == 'GET'
        assert content['path'] == '/api/v1/me'
        assert content['status'] == 200
        assert content['body']['user_id'] == 'u1'
        assert content['request_id'] == 'req-abc'

    def test_record_api_response_without_body(self, proof_session: ProofSession):
        artifact = proof_session.record_api_response(
            step=4,
            method='DELETE',
            path='/api/v1/workspaces/w1',
            status=204,
        )
        full_path = proof_session.scenario_dir / 'step04_api_delete_api_v1_workspaces_w1.json'
        content = json.loads(full_path.read_text())
        assert 'body' not in content
        assert content['status'] == 204

    def test_record_api_response_auto_description(self, proof_session: ProofSession):
        artifact = proof_session.record_api_response(
            step=1,
            method='POST',
            path='/api/v1/workspaces',
            status=202,
        )
        assert artifact.description == 'POST /api/v1/workspaces \u2192 202'

    def test_record_api_response_custom_description(self, proof_session: ProofSession):
        artifact = proof_session.record_api_response(
            step=1,
            method='GET',
            path='/health',
            status=200,
            description='Health check',
        )
        assert artifact.description == 'Health check'

    def test_record_api_response_metadata(self, proof_session: ProofSession):
        artifact = proof_session.record_api_response(
            step=5,
            method='PUT',
            path='/api/v1/file',
            status=200,
            request_id='req-xyz',
        )
        assert artifact.metadata['method'] == 'PUT'
        assert artifact.metadata['status'] == 200
        assert artifact.metadata['request_id'] == 'req-xyz'


class TestProofSessionLogEntry:
    def test_record_log_entry(self, proof_session: ProofSession):
        artifact = proof_session.record_log_entry(
            step=3,
            description='Provisioning timeout detected',
            log_text='2026-02-13 ERROR: timeout after 30s',
        )
        assert artifact.artifact_type == ArtifactType.LOG_ENTRY
        assert artifact.step_number == 3

        full_path = proof_session.scenario_dir / 'step03_log.txt'
        assert full_path.exists()
        assert 'timeout after 30s' in full_path.read_text()


class TestProofSessionScreenshot:
    @pytest.mark.asyncio
    async def test_capture_screenshot_success(
        self, capture_config: CaptureConfig,
    ):
        mock_browser = MagicMock(spec=BrowserCapture)
        mock_browser.screenshot = AsyncMock(
            return_value=capture_config.output_dir / 'S-002' / 'step01_screenshot.png',
        )

        session = ProofSession(
            capture_config, 'S-002', browser=mock_browser,
        )

        artifact = await session.capture_screenshot(
            step=1,
            description='Login page',
            url='http://localhost:5173/login',
        )
        assert artifact.artifact_type == ArtifactType.SCREENSHOT
        assert artifact.step_number == 1
        assert artifact.metadata['url'] == 'http://localhost:5173/login'
        mock_browser.screenshot.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_capture_screenshot_failure_raises(
        self, capture_config: CaptureConfig,
    ):
        mock_browser = MagicMock(spec=BrowserCapture)
        mock_browser.screenshot = AsyncMock(
            side_effect=RuntimeError('browser crashed'),
        )

        session = ProofSession(
            capture_config, 'S-003', browser=mock_browser,
        )

        with pytest.raises(RuntimeError, match='browser crashed'):
            await session.capture_screenshot(
                step=1, description='test', url='http://localhost:5173',
            )


class TestProofSessionFinalize:
    def test_finalize_writes_manifest(self, proof_session: ProofSession):
        proof_session.record_api_response(
            step=1, method='GET', path='/health', status=200,
        )
        proof_session.record_log_entry(
            step=2, description='test log', log_text='hello',
        )

        artifacts = proof_session.finalize()
        assert len(artifacts) == 2

        manifest_path = proof_session.scenario_dir / 'manifest.json'
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text())
        assert manifest['scenario_id'] == 'S-001'
        assert manifest['artifact_count'] == 2
        assert len(manifest['artifacts']) == 2

    def test_finalize_idempotent(self, proof_session: ProofSession):
        proof_session.record_api_response(
            step=1, method='GET', path='/health', status=200,
        )
        first = proof_session.finalize()
        second = proof_session.finalize()
        assert first == second

    def test_finalize_empty_session(self, proof_session: ProofSession):
        artifacts = proof_session.finalize()
        assert artifacts == ()

        manifest = json.loads(
            (proof_session.scenario_dir / 'manifest.json').read_text()
        )
        assert manifest['artifact_count'] == 0

    def test_scenario_dir_created(self, capture_config: CaptureConfig):
        session = ProofSession(capture_config, 'S-099')
        assert session.scenario_dir.exists()
        assert session.scenario_dir.name == 'S-099'


# ── BrowserCapture ────────────────────────────────────────────────


class TestBrowserCapture:
    @pytest.mark.asyncio
    async def test_screenshot_success(self, tmp_output: Path):
        config = CaptureConfig(output_dir=tmp_output)
        capture = BrowserCapture(config)

        output_path = tmp_output / 'test_screenshot.png'

        # Mock asyncio.create_subprocess_exec to simulate success.
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b'', b''))

        with patch('control_plane.app.testing.visual_proof.asyncio') as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            result = await capture.screenshot(
                'http://localhost:5173', output_path,
            )
            assert result == output_path

    @pytest.mark.asyncio
    async def test_screenshot_failure(self, tmp_output: Path):
        config = CaptureConfig(output_dir=tmp_output)
        capture = BrowserCapture(config)

        output_path = tmp_output / 'fail.png'

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b'', b'Error: browser launch failed'),
        )

        with patch('control_plane.app.testing.visual_proof.asyncio') as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            with pytest.raises(RuntimeError, match='browser launch failed'):
                await capture.screenshot('http://example.com', output_path)

    @pytest.mark.asyncio
    async def test_screenshot_creates_parent_dirs(self, tmp_output: Path):
        config = CaptureConfig(output_dir=tmp_output)
        capture = BrowserCapture(config)

        output_path = tmp_output / 'deep' / 'nested' / 'screenshot.png'

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b'', b''))

        with patch('control_plane.app.testing.visual_proof.asyncio') as mock_asyncio:
            mock_asyncio.create_subprocess_exec = AsyncMock(return_value=mock_proc)
            mock_asyncio.subprocess = asyncio.subprocess

            await capture.screenshot('http://localhost:5173', output_path)
            assert output_path.parent.exists()


# ── Helpers ───────────────────────────────────────────────────────


class TestHelpers:
    def test_safe_path(self):
        assert _safe_path('/api/v1/me') == 'api_v1_me'
        assert _safe_path('/api/v1/workspaces/{id}') == 'api_v1_workspaces_id'
        assert _safe_path('/health') == 'health'
        assert _safe_path('/') == ''

    def test_escape_js(self):
        assert _escape_js("hello") == "hello"
        assert _escape_js("it's") == "it\\'s"
        assert _escape_js("a\\b") == "a\\\\b"
        assert _escape_js("a\nb") == "a\\nb"
        assert _escape_js("a\rb") == "a\\rb"


# ── ProofReportBuilder ───────────────────────────────────────────


class TestProofReportBuilder:
    def test_header_with_pass(self):
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_header(passed=True)
        report = builder.build()
        assert '# S-001: Login Flow \u2714 PASSED' in report

    def test_header_with_fail(self):
        builder = ProofReportBuilder('S-002', 'Workspace Create')
        builder.add_header(passed=False)
        report = builder.build()
        assert '\u2718 FAILED' in report

    def test_header_with_timestamps(self):
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_header(
            started_at='2026-02-13T12:00:00+00:00',
            finished_at='2026-02-13T12:00:01+00:00',
            passed=True,
        )
        report = builder.build()
        assert '**Started:** 2026-02-13T12:00:00+00:00' in report
        assert '**Finished:** 2026-02-13T12:00:01+00:00' in report

    def test_summary_table(self):
        result = _make_result()
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_summary(result)
        report = builder.build()
        assert '| Total Steps | 2 |' in report
        assert '| Passed | 2 |' in report
        assert '| Verdict | PASS |' in report

    def test_step_result_pass(self):
        step = _make_step(outcome=StepOutcome.PASS)
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_step_result(step)
        report = builder.build()
        assert 'Step 1: GET /api/v1/me \u2714' in report
        assert '**Outcome:** pass' in report

    def test_step_result_fail_with_error(self):
        step = _make_step(
            outcome=StepOutcome.FAIL,
            actual_status=500,
            error_detail='Expected 200, got 500',
        )
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_step_result(step)
        report = builder.build()
        assert '\u2718' in report
        assert '**Error:** Expected 200, got 500' in report

    def test_step_result_with_artifacts(self):
        step = _make_step()
        artifacts = [
            EvidenceArtifact(
                artifact_type=ArtifactType.SCREENSHOT,
                step_number=1,
                description='Login page',
                file_path='S-001/step01_screenshot.png',
                timestamp='2026-02-13T12:00:00+00:00',
                scenario_id='S-001',
            ),
            EvidenceArtifact(
                artifact_type=ArtifactType.API_RESPONSE,
                step_number=1,
                description='API response',
                file_path='S-001/step01_api.json',
                timestamp='2026-02-13T12:00:00+00:00',
                scenario_id='S-001',
            ),
        ]
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_step_result(step, artifacts)
        report = builder.build()
        assert '**Evidence:**' in report
        assert '![Login page]' in report
        assert 'step01_api.json' in report

    def test_step_result_skip(self):
        step = _make_step(
            outcome=StepOutcome.SKIP,
            actual_status=None,
            error_detail='Skipped due to prior failure',
        )
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_step_result(step)
        report = builder.build()
        assert '\u23E9' in report

    def test_step_result_error(self):
        step = _make_step(
            outcome=StepOutcome.ERROR,
            actual_status=None,
            error_detail='ConnectError: connection refused',
        )
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_step_result(step)
        report = builder.build()
        assert '\u26A0' in report

    def test_step_result_missing_fields(self):
        step = _make_step(missing_fields=('user_id', 'email'))
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_step_result(step)
        report = builder.build()
        assert '**Missing fields:** user_id, email' in report

    def test_step_result_with_request_id(self):
        step = _make_step(request_id='req-abc-123')
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_step_result(step)
        report = builder.build()
        assert '`req-abc-123`' in report

    def test_footer_basic(self):
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_footer()
        report = builder.build()
        assert 'Generated by boring-ui scenario runner (K4)' in report

    def test_footer_with_artifact_index(self):
        artifacts = [
            EvidenceArtifact(
                artifact_type=ArtifactType.SCREENSHOT,
                step_number=1,
                description='Login page',
                file_path='S-001/step01.png',
                timestamp='2026-02-13T12:00:00+00:00',
                scenario_id='S-001',
            ),
            EvidenceArtifact(
                artifact_type=ArtifactType.API_RESPONSE,
                step_number=2,
                description='Me endpoint',
                file_path='S-001/step02.json',
                timestamp='2026-02-13T12:00:00+00:00',
                scenario_id='S-001',
            ),
        ]
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_footer(all_artifacts=artifacts)
        report = builder.build()
        assert '## Artifact Index' in report
        assert '| 1 | screenshot |' in report
        assert '| 2 | api_response |' in report

    def test_add_note(self):
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_note('> Known issue: flaky on CI.')
        report = builder.build()
        assert '> Known issue: flaky on CI.' in report

    def test_chaining(self):
        builder = ProofReportBuilder('S-001', 'Login Flow')
        result = builder.add_header(passed=True)
        assert result is builder

    def test_write(self, tmp_path: Path):
        builder = ProofReportBuilder('S-001', 'Login Flow')
        builder.add_header(passed=True)
        out = tmp_path / 'sub' / 'report.md'
        builder.write(out)
        assert out.exists()
        assert '# S-001: Login Flow' in out.read_text()


# ── build_proof_report ────────────────────────────────────────────


class TestBuildProofReport:
    def test_full_report(self):
        result = _make_result()
        artifacts = (
            EvidenceArtifact(
                artifact_type=ArtifactType.API_RESPONSE,
                step_number=1,
                description='Me endpoint',
                file_path='S-001/step01_api.json',
                timestamp='2026-02-13T12:00:00+00:00',
                scenario_id='S-001',
            ),
            EvidenceArtifact(
                artifact_type=ArtifactType.SCREENSHOT,
                step_number=2,
                description='Workspace page',
                file_path='S-001/step02_screenshot.png',
                timestamp='2026-02-13T12:00:00+00:00',
                scenario_id='S-001',
            ),
        )

        report = build_proof_report(result, artifacts)

        # Header
        assert '# S-001: Login Flow' in report
        assert '\u2714 PASSED' in report

        # Summary
        assert '| Total Steps | 2 |' in report
        assert '| Verdict | PASS |' in report

        # Steps
        assert 'Step 1: GET /api/v1/me' in report
        assert 'Step 2: POST /api/v1/workspaces' in report

        # Artifacts attached to steps
        assert 'step01_api.json' in report
        assert '![Workspace page]' in report

        # Artifact index
        assert '## Artifact Index' in report

        # Footer
        assert 'Generated by boring-ui scenario runner (K4)' in report

    def test_failed_report(self):
        steps = (
            _make_step(step_number=1, outcome=StepOutcome.PASS),
            _make_step(
                step_number=2,
                method='POST',
                path='/api/v1/workspaces',
                expected_status=202,
                actual_status=500,
                outcome=StepOutcome.FAIL,
                error_detail='Expected 202, got 500',
            ),
        )
        result = _make_result(steps=steps)
        report = build_proof_report(result)

        assert '\u2718 FAILED' in report
        assert '| Failed | 1 |' in report
        assert '| Verdict | FAIL |' in report

    def test_no_artifacts(self):
        result = _make_result()
        report = build_proof_report(result)
        assert '# S-001: Login Flow' in report
        assert '## Artifact Index' not in report

    def test_artifacts_grouped_by_step(self):
        result = _make_result()
        artifacts = (
            EvidenceArtifact(
                artifact_type=ArtifactType.API_RESPONSE,
                step_number=1,
                description='First API',
                file_path='S-001/step01_a.json',
                timestamp='2026-02-13T12:00:00+00:00',
                scenario_id='S-001',
            ),
            EvidenceArtifact(
                artifact_type=ArtifactType.SCREENSHOT,
                step_number=1,
                description='First screenshot',
                file_path='S-001/step01_b.png',
                timestamp='2026-02-13T12:00:00+00:00',
                scenario_id='S-001',
            ),
        )
        report = build_proof_report(result, artifacts)
        # Both artifacts should appear under step 1.
        assert 'step01_a.json' in report
        assert '![First screenshot]' in report


# ── _format_artifact ──────────────────────────────────────────────


class TestFormatArtifact:
    def test_screenshot_as_image(self):
        a = EvidenceArtifact(
            artifact_type=ArtifactType.SCREENSHOT,
            step_number=1,
            description='Login page',
            file_path='S-001/step01.png',
            timestamp='2026-02-13T12:00:00+00:00',
            scenario_id='S-001',
        )
        formatted = _format_artifact(a)
        assert formatted == '  - ![Login page](S-001/step01.png)'

    def test_api_response_as_link(self):
        a = EvidenceArtifact(
            artifact_type=ArtifactType.API_RESPONSE,
            step_number=2,
            description='Me response',
            file_path='S-001/step02.json',
            timestamp='2026-02-13T12:00:00+00:00',
            scenario_id='S-001',
        )
        formatted = _format_artifact(a)
        assert '[api_response]' in formatted
        assert '`S-001/step02.json`' in formatted

    def test_log_entry_format(self):
        a = EvidenceArtifact(
            artifact_type=ArtifactType.LOG_ENTRY,
            step_number=3,
            description='Timeout log',
            file_path='S-001/step03.txt',
            timestamp='2026-02-13T12:00:00+00:00',
            scenario_id='S-001',
        )
        formatted = _format_artifact(a)
        assert '[log_entry]' in formatted
        assert 'Timeout log' in formatted


# ── Integration with ScenarioResult ──────────────────────────────


class TestIntegration:
    def test_proof_session_with_scenario_result(
        self, capture_config: CaptureConfig,
    ):
        """Full integration: run a session, record evidence, build report."""
        session = ProofSession(capture_config, 'S-002')

        # Simulate recording evidence from a scenario result.
        result = _make_result(scenario_id='S-002', title='Workspace Create')

        for step in result.step_results:
            if step.actual_status is not None:
                session.record_api_response(
                    step=step.step_number,
                    method=step.method,
                    path=step.path,
                    status=step.actual_status,
                    body=step.response_body,
                    request_id=step.request_id,
                )

        artifacts = session.finalize()
        assert len(artifacts) == 2

        # Build report.
        report = build_proof_report(result, artifacts)
        assert '# S-002: Workspace Create' in report
        assert '## Artifact Index' in report
        assert '| 1 |' in report
        assert '| 2 |' in report

    def test_manifest_valid_json(self, proof_session: ProofSession):
        proof_session.record_api_response(
            step=1, method='GET', path='/health', status=200,
        )
        proof_session.finalize()

        manifest_path = proof_session.scenario_dir / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())

        # Validate manifest structure.
        assert 'scenario_id' in manifest
        assert 'artifact_count' in manifest
        assert 'finalized_at' in manifest
        assert 'artifacts' in manifest
        assert isinstance(manifest['artifacts'], list)
        assert manifest['artifacts'][0]['type'] == 'api_response'

    def test_multiple_scenarios(self, capture_config: CaptureConfig):
        """Multiple proof sessions use separate directories."""
        s1 = ProofSession(capture_config, 'S-001')
        s2 = ProofSession(capture_config, 'S-002')

        s1.record_api_response(step=1, method='GET', path='/a', status=200)
        s2.record_api_response(step=1, method='GET', path='/b', status=201)

        a1 = s1.finalize()
        a2 = s2.finalize()

        assert len(a1) == 1
        assert len(a2) == 1
        assert s1.scenario_dir != s2.scenario_dir
        assert (s1.scenario_dir / 'manifest.json').exists()
        assert (s2.scenario_dir / 'manifest.json').exists()
