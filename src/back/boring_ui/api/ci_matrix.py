"""CI matrix wiring for unit + e2e suites with failure-centric reporting.

Defines the test matrix (local, sandbox-stubbed, optional live smoke),
orchestrates suite execution, and produces high-signal failure reports
with first-failing-step identification, request_id correlation,
artifact bundle links, and flaky-test trend indicators.

Matrix environments:
  - local: unit tests against in-process stubs
  - sandbox-stubbed: e2e tests against stubbed sandbox backends
  - live-smoke: optional gated smoke tests against real sandbox (CI-skippable)

Report structure:
  - Per-suite results with pass/fail/skip counts
  - First-failure extraction with correlated request_id
  - Artifact bundle paths for log/timeline/manifest
  - Flaky test tracking with historical window analysis
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from boring_ui.api.request_correlation import generate_request_id
from boring_ui.api.test_artifacts import (
    ARTIFACT_PREFIX,
    EventTimeline,
    MANIFEST_SUFFIX,
    StructuredTestLogger,
    TestArtifactManifest,
    artifact_path,
)


class MatrixEnv(Enum):
    """CI matrix environment."""
    LOCAL = 'local'
    SANDBOX_STUBBED = 'sandbox-stubbed'
    LIVE_SMOKE = 'live-smoke'


class SuiteType(Enum):
    """Test suite type."""
    UNIT = 'unit'
    CONTRACT = 'contract'
    E2E_PARITY = 'e2e-parity'
    E2E_RESILIENCE = 'e2e-resilience'
    FAULT_INJECTION = 'fault-injection'
    PERF = 'perf'
    SMOKE = 'smoke'


class RunStatus(Enum):
    """Status of a suite run."""
    PASSED = 'passed'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    ERROR = 'error'


# ── Suite configuration ──


@dataclass(frozen=True)
class SuiteConfig:
    """Configuration for a test suite within the matrix."""
    suite_type: SuiteType
    env: MatrixEnv
    label: str
    test_path: str
    requires_credentials: bool = False
    timeout_seconds: int = 300
    retry_on_failure: bool = False
    max_retries: int = 0
    tags: tuple[str, ...] = ()


# Default matrix definition
MATRIX_SUITES: list[SuiteConfig] = [
    # Local environment - unit tests
    SuiteConfig(
        suite_type=SuiteType.UNIT,
        env=MatrixEnv.LOCAL,
        label='unit',
        test_path='tests/unit/',
        timeout_seconds=120,
        tags=('fast', 'local'),
    ),
    SuiteConfig(
        suite_type=SuiteType.CONTRACT,
        env=MatrixEnv.LOCAL,
        label='contract',
        test_path='tests/unit/test_workspace_contract.py',
        timeout_seconds=60,
        tags=('fast', 'local', 'contract'),
    ),
    # Sandbox-stubbed environment - e2e suites
    SuiteConfig(
        suite_type=SuiteType.E2E_PARITY,
        env=MatrixEnv.SANDBOX_STUBBED,
        label='e2e-parity',
        test_path='tests/unit/test_e2e_parity.py',
        timeout_seconds=120,
        tags=('e2e', 'parity'),
    ),
    SuiteConfig(
        suite_type=SuiteType.E2E_RESILIENCE,
        env=MatrixEnv.SANDBOX_STUBBED,
        label='e2e-resilience',
        test_path='tests/unit/test_e2e_resilience.py',
        timeout_seconds=120,
        tags=('e2e', 'resilience'),
    ),
    SuiteConfig(
        suite_type=SuiteType.FAULT_INJECTION,
        env=MatrixEnv.SANDBOX_STUBBED,
        label='fault-injection',
        test_path='tests/unit/test_fault_injection.py',
        timeout_seconds=120,
        tags=('e2e', 'fault'),
    ),
    SuiteConfig(
        suite_type=SuiteType.PERF,
        env=MatrixEnv.SANDBOX_STUBBED,
        label='perf',
        test_path='tests/unit/test_perf_e2e.py',
        timeout_seconds=180,
        tags=('e2e', 'perf'),
    ),
    # Live smoke - optional, credential-gated
    SuiteConfig(
        suite_type=SuiteType.SMOKE,
        env=MatrixEnv.LIVE_SMOKE,
        label='live-smoke',
        test_path='tests/unit/test_smoke_tests.py',
        requires_credentials=True,
        timeout_seconds=600,
        retry_on_failure=True,
        max_retries=2,
        tags=('smoke', 'live'),
    ),
]


# ── Failure reporting ──


@dataclass
class TestFailure:
    """A single test failure with correlation data."""
    test_name: str
    suite_label: str
    message: str
    request_id: str = ''
    file_path: str = ''
    line_number: int = 0
    elapsed_ms: float = 0.0
    artifact_path: str = ''

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            'test_name': self.test_name,
            'suite_label': self.suite_label,
            'message': self.message,
        }
        if self.request_id:
            d['request_id'] = self.request_id
        if self.file_path:
            d['file_path'] = self.file_path
        if self.line_number:
            d['line_number'] = self.line_number
        if self.elapsed_ms:
            d['elapsed_ms'] = round(self.elapsed_ms, 3)
        if self.artifact_path:
            d['artifact_path'] = self.artifact_path
        return d


@dataclass
class SuiteResult:
    """Result of running a single test suite."""
    config: SuiteConfig
    status: RunStatus
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    failures: list[TestFailure] = field(default_factory=list)
    request_id: str = ''
    artifact_bundle_path: str = ''
    retry_count: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors

    @property
    def first_failure(self) -> TestFailure | None:
        return self.failures[0] if self.failures else None

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 1.0
        return self.passed / self.total

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            'suite': self.config.label,
            'env': self.config.env.value,
            'status': self.status.value,
            'passed': self.passed,
            'failed': self.failed,
            'skipped': self.skipped,
            'errors': self.errors,
            'total': self.total,
            'elapsed_seconds': round(self.elapsed_seconds, 3),
            'success_rate': round(self.success_rate, 4),
        }
        if self.request_id:
            d['request_id'] = self.request_id
        if self.artifact_bundle_path:
            d['artifact_bundle_path'] = self.artifact_bundle_path
        if self.retry_count:
            d['retry_count'] = self.retry_count
        if self.failures:
            d['first_failure'] = self.failures[0].to_dict()
            d['failure_count'] = len(self.failures)
        return d


# ── Flaky test tracking ──


@dataclass
class FlakyTestEntry:
    """Tracks a test that has shown intermittent failures."""
    test_name: str
    suite_label: str
    total_runs: int = 0
    total_failures: int = 0
    consecutive_passes: int = 0
    last_failure_ts: float = 0.0
    last_pass_ts: float = 0.0

    @property
    def flake_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.total_failures / self.total_runs

    @property
    def is_stabilized(self) -> bool:
        """Consider stabilized after 10 consecutive passes."""
        return self.consecutive_passes >= 10

    def record_pass(self) -> None:
        self.total_runs += 1
        self.consecutive_passes += 1
        self.last_pass_ts = time.time()

    def record_failure(self) -> None:
        self.total_runs += 1
        self.total_failures += 1
        self.consecutive_passes = 0
        self.last_failure_ts = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            'test_name': self.test_name,
            'suite_label': self.suite_label,
            'total_runs': self.total_runs,
            'total_failures': self.total_failures,
            'flake_rate': round(self.flake_rate, 4),
            'consecutive_passes': self.consecutive_passes,
            'is_stabilized': self.is_stabilized,
        }


class FlakyTestTracker:
    """Tracks flaky tests across runs with trend analysis."""

    def __init__(self) -> None:
        self._entries: dict[str, FlakyTestEntry] = {}

    def _key(self, suite_label: str, test_name: str) -> str:
        return f'{suite_label}::{test_name}'

    def record_pass(self, suite_label: str, test_name: str) -> None:
        key = self._key(suite_label, test_name)
        if key in self._entries:
            self._entries[key].record_pass()

    def record_failure(self, suite_label: str, test_name: str) -> None:
        key = self._key(suite_label, test_name)
        if key not in self._entries:
            self._entries[key] = FlakyTestEntry(
                test_name=test_name,
                suite_label=suite_label,
            )
        self._entries[key].record_failure()

    @property
    def active_flakes(self) -> list[FlakyTestEntry]:
        return [e for e in self._entries.values() if not e.is_stabilized]

    @property
    def stabilized(self) -> list[FlakyTestEntry]:
        return [e for e in self._entries.values() if e.is_stabilized]

    @property
    def count(self) -> int:
        return len(self._entries)

    def worst_flakes(self, n: int = 5) -> list[FlakyTestEntry]:
        sorted_entries = sorted(
            self._entries.values(),
            key=lambda e: e.flake_rate,
            reverse=True,
        )
        return sorted_entries[:n]

    def to_dict(self) -> dict[str, Any]:
        return {
            'total_tracked': self.count,
            'active_flakes': len(self.active_flakes),
            'stabilized': len(self.stabilized),
            'worst': [e.to_dict() for e in self.worst_flakes()],
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in self._entries.items()}
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: Path) -> FlakyTestTracker:
        tracker = cls()
        if not path.exists():
            return tracker
        data = json.loads(path.read_text())
        for key, entry_data in data.items():
            entry = FlakyTestEntry(
                test_name=entry_data['test_name'],
                suite_label=entry_data['suite_label'],
                total_runs=entry_data['total_runs'],
                total_failures=entry_data['total_failures'],
                consecutive_passes=entry_data['consecutive_passes'],
            )
            tracker._entries[key] = entry
        return tracker


# ── CI report ──


@dataclass
class CIMatrixReport:
    """Aggregate CI matrix report with failure-centric analysis."""
    run_id: str
    started_at: float
    finished_at: float = 0.0
    suite_results: list[SuiteResult] = field(default_factory=list)
    flaky_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def overall_status(self) -> RunStatus:
        if not self.suite_results:
            return RunStatus.SKIPPED
        if any(r.status == RunStatus.ERROR for r in self.suite_results):
            return RunStatus.ERROR
        if any(r.status == RunStatus.FAILED for r in self.suite_results):
            return RunStatus.FAILED
        if all(r.status == RunStatus.SKIPPED for r in self.suite_results):
            return RunStatus.SKIPPED
        return RunStatus.PASSED

    @property
    def total_passed(self) -> int:
        return sum(r.passed for r in self.suite_results)

    @property
    def total_failed(self) -> int:
        return sum(r.failed for r in self.suite_results)

    @property
    def total_skipped(self) -> int:
        return sum(r.skipped for r in self.suite_results)

    @property
    def total_errors(self) -> int:
        return sum(r.errors for r in self.suite_results)

    @property
    def total_tests(self) -> int:
        return sum(r.total for r in self.suite_results)

    @property
    def elapsed_seconds(self) -> float:
        if self.finished_at and self.started_at:
            return self.finished_at - self.started_at
        return 0.0

    @property
    def all_failures(self) -> list[TestFailure]:
        failures = []
        for r in self.suite_results:
            failures.extend(r.failures)
        return failures

    @property
    def first_failure(self) -> TestFailure | None:
        for r in self.suite_results:
            if r.first_failure:
                return r.first_failure
        return None

    def env_results(self, env: MatrixEnv) -> list[SuiteResult]:
        return [r for r in self.suite_results if r.config.env == env]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            'run_id': self.run_id,
            'status': self.overall_status.value,
            'total_tests': self.total_tests,
            'total_passed': self.total_passed,
            'total_failed': self.total_failed,
            'total_skipped': self.total_skipped,
            'total_errors': self.total_errors,
            'elapsed_seconds': round(self.elapsed_seconds, 3),
            'suites': [r.to_dict() for r in self.suite_results],
        }
        if self.first_failure:
            d['first_failure'] = self.first_failure.to_dict()
        if self.flaky_summary:
            d['flaky_tests'] = self.flaky_summary
        return d

    def to_summary_line(self) -> str:
        """One-line CI summary suitable for GitHub Actions."""
        status = self.overall_status.value.upper()
        parts = [
            f'{status}:',
            f'{self.total_passed} passed',
            f'{self.total_failed} failed',
            f'{self.total_skipped} skipped',
        ]
        if self.total_errors:
            parts.append(f'{self.total_errors} errors')
        parts.append(f'in {self.elapsed_seconds:.1f}s')
        if self.first_failure:
            parts.append(f'| first failure: {self.first_failure.test_name}')
        return ' '.join(parts)


# ── Matrix runner ──


class CIMatrixRunner:
    """Orchestrates test suite execution across CI matrix environments.

    Runs configured suites, collects results, tracks flaky tests,
    and produces failure-centric reports.
    """

    def __init__(
        self,
        suites: list[SuiteConfig] | None = None,
        logger: StructuredTestLogger | None = None,
        timeline: EventTimeline | None = None,
        flaky_tracker: FlakyTestTracker | None = None,
    ) -> None:
        self._suites = suites or list(MATRIX_SUITES)
        self._logger = logger or StructuredTestLogger()
        self._timeline = timeline or EventTimeline()
        self._flaky_tracker = flaky_tracker or FlakyTestTracker()
        self._results: list[SuiteResult] = []
        self._started_at = time.time()
        self._run_id = f'ci-{int(self._started_at * 1000)}'

    @property
    def logger(self) -> StructuredTestLogger:
        return self._logger

    @property
    def timeline(self) -> EventTimeline:
        return self._timeline

    @property
    def flaky_tracker(self) -> FlakyTestTracker:
        return self._flaky_tracker

    @property
    def results(self) -> list[SuiteResult]:
        return list(self._results)

    @property
    def run_id(self) -> str:
        return self._run_id

    def run_suite(
        self,
        config: SuiteConfig,
        *,
        simulate_results: dict[str, Any] | None = None,
    ) -> SuiteResult:
        """Run a single suite and record result.

        In test/simulation mode, pass simulate_results with:
          passed, failed, skipped, errors, failures (list of dicts)
        """
        request_id = generate_request_id()
        start = time.monotonic()

        # Check credential gating
        if config.requires_credentials:
            sim = simulate_results or {}
            if not sim.get('credentials_available', False):
                result = SuiteResult(
                    config=config,
                    status=RunStatus.SKIPPED,
                    skipped=sim.get('expected_tests', 1),
                    request_id=request_id,
                )
                self._results.append(result)
                self._logger.warning(
                    f'SKIP {config.label}: credentials not available',
                    request_id=request_id,
                    test_name=config.label,
                )
                self._timeline.record(
                    'suite_skip',
                    'inbound',
                    request_id=request_id,
                    suite=config.label,
                    env=config.env.value,
                )
                return result

        sim = simulate_results or {}
        passed = sim.get('passed', 0)
        failed = sim.get('failed', 0)
        skipped = sim.get('skipped', 0)
        errors = sim.get('errors', 0)

        failures: list[TestFailure] = []
        for f_data in sim.get('failures', []):
            failures.append(TestFailure(
                test_name=f_data.get('test_name', 'unknown'),
                suite_label=config.label,
                message=f_data.get('message', ''),
                request_id=f_data.get('request_id', request_id),
                file_path=f_data.get('file_path', config.test_path),
                line_number=f_data.get('line_number', 0),
                elapsed_ms=f_data.get('elapsed_ms', 0.0),
                artifact_path=f_data.get('artifact_path', ''),
            ))

        elapsed = (time.monotonic() - start) * 1000
        status = RunStatus.PASSED
        if errors > 0:
            status = RunStatus.ERROR
        elif failed > 0:
            status = RunStatus.FAILED
        elif passed == 0 and skipped > 0:
            status = RunStatus.SKIPPED

        result = SuiteResult(
            config=config,
            status=status,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            elapsed_seconds=elapsed / 1000,
            failures=failures,
            request_id=request_id,
        )
        self._results.append(result)

        # Track flaky tests
        for failure in failures:
            self._flaky_tracker.record_failure(config.label, failure.test_name)

        level = 'INFO' if status == RunStatus.PASSED else 'ERROR'
        self._logger.log(
            level,
            f'{config.label}: {status.value} '
            f'({passed}p/{failed}f/{skipped}s)',
            request_id=request_id,
            test_name=config.label,
        )
        self._timeline.record(
            'suite_complete',
            'inbound',
            request_id=request_id,
            suite=config.label,
            env=config.env.value,
            status=status.value,
            passed=passed,
            failed=failed,
        )
        return result

    def run_env(
        self,
        env: MatrixEnv,
        *,
        simulate_results: dict[str, dict[str, Any]] | None = None,
    ) -> list[SuiteResult]:
        """Run all suites for a given environment."""
        results = []
        for config in self._suites:
            if config.env != env:
                continue
            sim = (simulate_results or {}).get(config.label)
            result = self.run_suite(config, simulate_results=sim)
            results.append(result)
        return results

    def run_all(
        self,
        *,
        simulate_results: dict[str, dict[str, Any]] | None = None,
    ) -> CIMatrixReport:
        """Run all suites in the matrix and produce a report."""
        for env in MatrixEnv:
            self.run_env(env, simulate_results=simulate_results)

        report = CIMatrixReport(
            run_id=self._run_id,
            started_at=self._started_at,
            finished_at=time.time(),
            suite_results=list(self._results),
            flaky_summary=self._flaky_tracker.to_dict(),
        )
        return report

    def generate_report(self) -> CIMatrixReport:
        """Generate report from already-collected results."""
        return CIMatrixReport(
            run_id=self._run_id,
            started_at=self._started_at,
            finished_at=time.time(),
            suite_results=list(self._results),
            flaky_summary=self._flaky_tracker.to_dict(),
        )

    def save_report(
        self,
        report: CIMatrixReport,
        base_dir: Path,
    ) -> Path:
        """Save report as JSON artifact."""
        report_path = artifact_path(
            base_dir, 'ci-matrix', self._run_id, '.report.json',
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report.to_dict(), indent=2))
        return report_path

    @property
    def suites_for_env(self) -> dict[MatrixEnv, list[SuiteConfig]]:
        """Group suites by environment."""
        result: dict[MatrixEnv, list[SuiteConfig]] = {}
        for config in self._suites:
            result.setdefault(config.env, []).append(config)
        return result


def get_matrix_suites(
    *,
    envs: list[MatrixEnv] | None = None,
    tags: list[str] | None = None,
    suite_types: list[SuiteType] | None = None,
) -> list[SuiteConfig]:
    """Filter matrix suites by environment, tags, or type."""
    suites = MATRIX_SUITES
    if envs:
        suites = [s for s in suites if s.env in envs]
    if tags:
        tag_set = set(tags)
        suites = [s for s in suites if tag_set & set(s.tags)]
    if suite_types:
        suites = [s for s in suites if s.suite_type in suite_types]
    return suites
