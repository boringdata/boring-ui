"""Gated live sandbox smoke tests.

Provides credential-gated smoke test definitions for deploy, health,
and minimal exec flows. Tests are skipped when live credentials are
not available (CI-friendly gating).

Smoke test categories:
  - Deploy: verify sandbox app starts and serves health endpoint
  - Health: verify service readiness and version endpoints
  - Exec: verify minimal session create/terminate lifecycle
  - Files: verify basic file list/read via delegation
  - WS: verify WebSocket connect/close handshake

Each smoke test produces structured step logs with request_id
correlation and retained artifact bundles.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from boring_ui.api.request_correlation import generate_request_id
from boring_ui.api.test_artifacts import (
    EventTimeline,
    LOG_SUFFIX,
    MANIFEST_SUFFIX,
    TIMELINE_SUFFIX,
    TestArtifactManifest,
    StructuredTestLogger,
    artifact_path,
)


class SmokeCategory(Enum):
    """Category of smoke test."""
    DEPLOY = 'deploy'
    HEALTH = 'health'
    EXEC = 'exec'
    FILES = 'files'
    WS = 'ws'


class SmokeOutcome(Enum):
    """Outcome of a smoke test step."""
    PASS = 'pass'
    FAIL = 'fail'
    SKIP = 'skip'


class GateStatus(Enum):
    """Whether live credentials are available."""
    AVAILABLE = 'available'
    MISSING = 'missing'
    EXPIRED = 'expired'


@dataclass(frozen=True)
class SmokeStep:
    """A single smoke test step."""
    name: str
    category: SmokeCategory
    description: str
    requires_credentials: bool = True


@dataclass
class SmokeStepResult:
    """Result of executing a single smoke test step."""
    step: SmokeStep
    outcome: SmokeOutcome
    request_id: str = ''
    elapsed_ms: float = 0.0
    message: str = ''
    response_status: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.outcome == SmokeOutcome.PASS

    @property
    def skipped(self) -> bool:
        return self.outcome == SmokeOutcome.SKIP

    def to_dict(self) -> dict:
        d = {
            'step': self.step.name,
            'category': self.step.category.value,
            'outcome': self.outcome.value,
            'request_id': self.request_id,
            'elapsed_ms': round(self.elapsed_ms, 3),
        }
        if self.message:
            d['message'] = self.message
        if self.response_status:
            d['response_status'] = self.response_status
        if self.extra:
            d['extra'] = self.extra
        return d


# ── Credential gate ──


@dataclass
class CredentialGate:
    """Checks whether live sandbox credentials are available.

    In CI, credentials are injected via environment variables.
    When missing, smoke tests that require them are skipped.
    """
    api_token: str = ''
    base_url: str = ''
    sprite_name: str = ''

    @property
    def status(self) -> GateStatus:
        if not self.api_token:
            return GateStatus.MISSING
        if not self.base_url:
            return GateStatus.MISSING
        return GateStatus.AVAILABLE

    @property
    def is_available(self) -> bool:
        return self.status == GateStatus.AVAILABLE

    def to_dict(self) -> dict:
        return {
            'status': self.status.value,
            'has_token': bool(self.api_token),
            'has_url': bool(self.base_url),
            'has_sprite': bool(self.sprite_name),
        }


# ── Smoke test definitions ──


DEPLOY_STEPS = [
    SmokeStep('app_startup', SmokeCategory.DEPLOY, 'Verify app starts', requires_credentials=False),
    SmokeStep('health_endpoint', SmokeCategory.DEPLOY, 'Check /health endpoint', requires_credentials=False),
]

HEALTH_STEPS = [
    SmokeStep('readiness', SmokeCategory.HEALTH, 'Check /api/ready'),
    SmokeStep('version', SmokeCategory.HEALTH, 'Check /api/version'),
    SmokeStep('services_health', SmokeCategory.HEALTH, 'Check upstream services health'),
]

EXEC_STEPS = [
    SmokeStep('create_session', SmokeCategory.EXEC, 'Create exec session'),
    SmokeStep('list_sessions', SmokeCategory.EXEC, 'List sessions'),
    SmokeStep('terminate_session', SmokeCategory.EXEC, 'Terminate session'),
]

FILES_STEPS = [
    SmokeStep('list_tree', SmokeCategory.FILES, 'List file tree'),
    SmokeStep('read_file', SmokeCategory.FILES, 'Read a file'),
]

WS_STEPS = [
    SmokeStep('ws_connect', SmokeCategory.WS, 'WebSocket connect handshake'),
    SmokeStep('ws_close', SmokeCategory.WS, 'WebSocket clean close'),
]

ALL_SMOKE_STEPS = {
    SmokeCategory.DEPLOY: DEPLOY_STEPS,
    SmokeCategory.HEALTH: HEALTH_STEPS,
    SmokeCategory.EXEC: EXEC_STEPS,
    SmokeCategory.FILES: FILES_STEPS,
    SmokeCategory.WS: WS_STEPS,
}


# ── Smoke test runner ──


class SmokeTestRunner:
    """Runs gated smoke tests with structured logging.

    Steps requiring credentials are automatically skipped when
    the credential gate reports MISSING or EXPIRED.
    """

    def __init__(
        self,
        gate: CredentialGate | None = None,
        logger: StructuredTestLogger | None = None,
        timeline: EventTimeline | None = None,
    ) -> None:
        self._gate = gate or CredentialGate()
        self._logger = logger or StructuredTestLogger()
        self._timeline = timeline or EventTimeline()
        self._results: list[SmokeStepResult] = []
        self._started_at = time.time()
        self._step_handlers: dict[str, Callable[[SmokeStep], SmokeStepResult]] = {}

    @classmethod
    def from_env(
        cls,
        *,
        logger: StructuredTestLogger | None = None,
        timeline: EventTimeline | None = None,
    ) -> SmokeTestRunner:
        """Create a runner with credential gate populated from environment."""
        return cls(
            gate=CredentialGate(
                api_token=os.getenv('SPRITES_API_TOKEN', '').strip(),
                base_url=os.getenv('SPRITES_BASE_URL', '').strip(),
                sprite_name=os.getenv('SPRITES_SPRITE_NAME', '').strip(),
            ),
            logger=logger,
            timeline=timeline,
        )

    @property
    def gate(self) -> CredentialGate:
        return self._gate

    @property
    def logger(self) -> StructuredTestLogger:
        return self._logger

    @property
    def timeline(self) -> EventTimeline:
        return self._timeline

    @property
    def results(self) -> list[SmokeStepResult]:
        return list(self._results)

    def execute_step(
        self,
        step: SmokeStep,
        *,
        outcome: SmokeOutcome = SmokeOutcome.PASS,
        response_status: int = 200,
        message: str = '',
        extra: dict | None = None,
    ) -> SmokeStepResult:
        """Execute a smoke test step with automatic credential gating."""
        request_id = generate_request_id()
        start = time.monotonic()

        # Auto-skip if credentials required but not available
        if step.requires_credentials and not self._gate.is_available:
            result = SmokeStepResult(
                step=step,
                outcome=SmokeOutcome.SKIP,
                request_id=request_id,
                message='Credentials not available',
            )
            self._results.append(result)
            self._logger.warning(
                f'SKIP {step.name}: credentials not available',
                request_id=request_id,
                test_name=step.name,
            )
            return result

        elapsed = (time.monotonic() - start) * 1000
        result = SmokeStepResult(
            step=step,
            outcome=outcome,
            request_id=request_id,
            elapsed_ms=elapsed,
            response_status=response_status,
            message=message,
            extra=extra or {},
        )
        self._results.append(result)

        level = 'INFO' if result.passed else 'ERROR'
        self._logger.log(
            level,
            f'{step.name}: {outcome.value}',
            request_id=request_id,
            test_name=step.name,
            step=step.name,
            category=step.category.value,
            response_status=response_status,
            elapsed_ms=round(elapsed, 3),
            **(extra or {}),
        )
        self._timeline.record(
            'smoke_test',
            'inbound',
            request_id=request_id,
            step=step.name,
            outcome=outcome.value,
        )
        return result

    def execute_command_step(
        self,
        step: SmokeStep,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int = 120,
    ) -> SmokeStepResult:
        """Execute a shell command as a smoke step with credential gating."""
        if step.requires_credentials and not self._gate.is_available:
            return self.execute_step(step, outcome=SmokeOutcome.SKIP)

        request_id = generate_request_id()
        started = time.monotonic()

        self._timeline.record(
            'smoke_command_start',
            'outbound',
            request_id=request_id,
            step=step.name,
            command=' '.join(command),
        )
        try:
            proc = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            elapsed = (time.monotonic() - started) * 1000
            outcome = SmokeOutcome.PASS if proc.returncode == 0 else SmokeOutcome.FAIL
            result = SmokeStepResult(
                step=step,
                outcome=outcome,
                request_id=request_id,
                elapsed_ms=elapsed,
                response_status=proc.returncode,
                message=(proc.stderr or proc.stdout).strip()[:4000],
                extra={'command': command, 'stdout': proc.stdout, 'stderr': proc.stderr},
            )
            self._results.append(result)
            self._logger.log(
                'INFO' if outcome == SmokeOutcome.PASS else 'ERROR',
                f'{step.name}: {outcome.value}',
                request_id=request_id,
                test_name=step.name,
                step=step.name,
                category=step.category.value,
                return_code=proc.returncode,
                elapsed_ms=round(elapsed, 3),
            )
            self._timeline.record(
                'smoke_command_end',
                'inbound',
                request_id=request_id,
                step=step.name,
                outcome=outcome.value,
                return_code=proc.returncode,
            )
            return result
        except subprocess.TimeoutExpired as exc:
            elapsed = (time.monotonic() - started) * 1000
            result = SmokeStepResult(
                step=step,
                outcome=SmokeOutcome.FAIL,
                request_id=request_id,
                elapsed_ms=elapsed,
                message=f'Command timed out after {timeout_seconds}s',
                extra={'command': command, 'stdout': exc.stdout or '', 'stderr': exc.stderr or ''},
            )
            self._results.append(result)
            self._logger.error(
                f'{step.name}: timeout',
                request_id=request_id,
                test_name=step.name,
                step=step.name,
                category=step.category.value,
                timeout_seconds=timeout_seconds,
            )
            self._timeline.record(
                'smoke_command_timeout',
                'inbound',
                request_id=request_id,
                step=step.name,
            )
            return result

    def register_step_handler(
        self,
        step_name: str,
        handler: Callable[[SmokeStep], SmokeStepResult],
    ) -> None:
        """Register an executor for a specific smoke step name."""
        self._step_handlers[step_name] = handler

    def run_category(self, category: SmokeCategory) -> list[SmokeStepResult]:
        """Run all steps in a smoke test category."""
        steps = ALL_SMOKE_STEPS.get(category, [])
        results = []
        for step in steps:
            handler = self._step_handlers.get(step.name)
            if handler:
                before_count = len(self._results)
                result = handler(step)
                # If handler didn't record via execute_step/execute_command_step,
                # record exactly once for this invocation.
                if len(self._results) == before_count:
                    self._results.append(result)
            else:
                # Never auto-pass in run mode; missing handlers are explicit failures.
                result = self.execute_step(
                    step,
                    outcome=SmokeOutcome.FAIL,
                    response_status=500,
                    message='No smoke step handler registered',
                )
            results.append(result)
        return results

    def run_all(self) -> None:
        """Run all smoke test categories."""
        for category in ALL_SMOKE_STEPS:
            self.run_category(category)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self._results if r.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self._results if r.outcome == SmokeOutcome.FAIL)

    @property
    def skip_count(self) -> int:
        return sum(1 for r in self._results if r.skipped)

    @property
    def all_passed_or_skipped(self) -> bool:
        return self.fail_count == 0

    def summary(self) -> dict:
        return {
            'gate': self._gate.to_dict(),
            'total_steps': len(self._results),
            'passed': self.pass_count,
            'failed': self.fail_count,
            'skipped': self.skip_count,
            'all_passed_or_skipped': self.all_passed_or_skipped,
            'results': [r.to_dict() for r in self._results],
        }

    def save_artifact_bundle(
        self,
        base_dir: Path,
        *,
        suite_name: str = 'live-smoke',
        run_id: str | None = None,
    ) -> TestArtifactManifest:
        """Persist logs/timelines/summary + manifest for CI/live runs."""
        resolved_run_id = run_id or f'run-{int(time.time() * 1000)}'
        log_path = artifact_path(base_dir, suite_name, resolved_run_id, LOG_SUFFIX)
        timeline_path = artifact_path(base_dir, suite_name, resolved_run_id, TIMELINE_SUFFIX)
        summary_path = artifact_path(base_dir, suite_name, resolved_run_id, '.summary.json')
        manifest_path = artifact_path(base_dir, suite_name, resolved_run_id, MANIFEST_SUFFIX)

        self._logger.save(log_path)
        self._timeline.save(timeline_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(self.summary(), indent=2))

        manifest = TestArtifactManifest(
            test_suite=suite_name,
            run_id=resolved_run_id,
            started_at=self._started_at,
        )
        manifest.add_artifact('structured_log', str(log_path), 'jsonl')
        manifest.add_artifact('timeline', str(timeline_path), 'timeline')
        manifest.add_artifact('summary', str(summary_path), 'summary')
        manifest.finish(
            summary={
                'passed': self.pass_count,
                'failed': self.fail_count,
                'skipped': self.skip_count,
                'all_passed_or_skipped': self.all_passed_or_skipped,
            }
        )
        manifest.save(manifest_path)
        return manifest
