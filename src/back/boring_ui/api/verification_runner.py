"""One-command verification runner for unit + e2e + smoke suites.

Provides a single orchestrator that runs comprehensive unit tests,
deterministic e2e suites, fault injection, and optional live smoke checks,
then emits a unified summary with links to detailed log/artifact bundles.

Usage (programmatic):
    runner = VerificationRunner.from_defaults()
    report = runner.run_all()
    runner.save_bundle(report, Path('./artifacts'))

The runner orchestrates all registered suites through the CI matrix,
captures structured logs and event timelines, and produces a unified
verification report suitable for go/no-go decisions.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from boring_ui.api.ci_matrix import (
    CIMatrixReport,
    CIMatrixRunner,
    FlakyTestTracker,
    MatrixEnv,
    MATRIX_SUITES,
    RunStatus,
    SuiteConfig,
    SuiteResult,
    SuiteType,
)
from boring_ui.api.test_artifacts import (
    ARTIFACT_PREFIX,
    EventTimeline,
    LOG_SUFFIX,
    MANIFEST_SUFFIX,
    StructuredTestLogger,
    TestArtifactManifest,
    TIMELINE_SUFFIX,
    artifact_path,
)
from boring_ui.api.slo_report import (
    SLOEvidence,
    SLOThresholds,
    evaluate_v0_slos,
    save_slo_report,
)


class VerificationVerdict(Enum):
    """Overall verification verdict."""
    GO = 'go'
    NO_GO = 'no-go'
    INCOMPLETE = 'incomplete'


class PhaseStatus(Enum):
    """Status of a verification phase."""
    PASSED = 'passed'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    NOT_RUN = 'not-run'


# ── Phase definitions ──


@dataclass(frozen=True)
class VerificationPhase:
    """A phase in the verification pipeline."""
    name: str
    label: str
    suite_types: tuple[SuiteType, ...]
    env: MatrixEnv
    required_for_go: bool = True
    description: str = ''


VERIFICATION_PHASES: list[VerificationPhase] = [
    VerificationPhase(
        name='unit',
        label='Unit Tests',
        suite_types=(SuiteType.UNIT, SuiteType.CONTRACT),
        env=MatrixEnv.LOCAL,
        required_for_go=True,
        description='Core unit tests and contract verification',
    ),
    VerificationPhase(
        name='e2e',
        label='E2E Suites',
        suite_types=(
            SuiteType.E2E_PARITY,
            SuiteType.E2E_RESILIENCE,
            SuiteType.FAULT_INJECTION,
        ),
        env=MatrixEnv.SANDBOX_STUBBED,
        required_for_go=True,
        description='Parity, resilience, and fault injection e2e suites',
    ),
    VerificationPhase(
        name='perf',
        label='Performance',
        suite_types=(SuiteType.PERF,),
        env=MatrixEnv.SANDBOX_STUBBED,
        required_for_go=False,
        description='Performance and load testing',
    ),
    VerificationPhase(
        name='smoke',
        label='Live Smoke',
        suite_types=(SuiteType.SMOKE,),
        env=MatrixEnv.LIVE_SMOKE,
        required_for_go=False,
        description='Optional credential-gated live smoke tests',
    ),
]


# ── Phase result ──


@dataclass
class PhaseResult:
    """Result of running a verification phase."""
    phase: VerificationPhase
    status: PhaseStatus
    suite_results: list[SuiteResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0

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
    def total_tests(self) -> int:
        return sum(r.total for r in self.suite_results)

    def to_dict(self) -> dict[str, Any]:
        return {
            'phase': self.phase.name,
            'label': self.phase.label,
            'status': self.status.value,
            'required_for_go': self.phase.required_for_go,
            'total_tests': self.total_tests,
            'passed': self.total_passed,
            'failed': self.total_failed,
            'skipped': self.total_skipped,
            'elapsed_seconds': round(self.elapsed_seconds, 3),
            'suites': [r.to_dict() for r in self.suite_results],
        }


# ── Verification report ──


@dataclass
class VerificationReport:
    """Unified verification report."""
    run_id: str
    started_at: float
    finished_at: float = 0.0
    phase_results: list[PhaseResult] = field(default_factory=list)
    matrix_report: CIMatrixReport | None = None
    flaky_summary: dict[str, Any] = field(default_factory=dict)
    slo_report: dict[str, Any] = field(default_factory=dict)
    artifact_paths: dict[str, str] = field(default_factory=dict)

    @property
    def verdict(self) -> VerificationVerdict:
        if not self.phase_results:
            return VerificationVerdict.INCOMPLETE
        required_phases = [
            p for p in self.phase_results if p.phase.required_for_go
        ]
        if not required_phases:
            return VerificationVerdict.INCOMPLETE
        if any(p.status == PhaseStatus.NOT_RUN for p in required_phases):
            return VerificationVerdict.INCOMPLETE
        if any(p.status == PhaseStatus.FAILED for p in required_phases):
            return VerificationVerdict.NO_GO
        return VerificationVerdict.GO

    @property
    def total_tests(self) -> int:
        return sum(p.total_tests for p in self.phase_results)

    @property
    def total_passed(self) -> int:
        return sum(p.total_passed for p in self.phase_results)

    @property
    def total_failed(self) -> int:
        return sum(p.total_failed for p in self.phase_results)

    @property
    def total_skipped(self) -> int:
        return sum(p.total_skipped for p in self.phase_results)

    @property
    def elapsed_seconds(self) -> float:
        if self.finished_at and self.started_at:
            return self.finished_at - self.started_at
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            'run_id': self.run_id,
            'verdict': self.verdict.value,
            'total_tests': self.total_tests,
            'total_passed': self.total_passed,
            'total_failed': self.total_failed,
            'total_skipped': self.total_skipped,
            'elapsed_seconds': round(self.elapsed_seconds, 3),
            'phases': [p.to_dict() for p in self.phase_results],
        }
        if self.flaky_summary:
            d['flaky_tests'] = self.flaky_summary
        if self.slo_report:
            d['slo_report'] = self.slo_report
        if self.artifact_paths:
            d['artifacts'] = self.artifact_paths
        return d

    def to_summary_line(self) -> str:
        """One-line verdict suitable for terminal/CI output."""
        verdict = self.verdict.value.upper()
        parts = [
            f'VERDICT: {verdict}',
            f'| {self.total_passed} passed',
            f'{self.total_failed} failed',
            f'{self.total_skipped} skipped',
            f'in {self.elapsed_seconds:.1f}s',
        ]
        return ' '.join(parts)

    def phase_by_name(self, name: str) -> PhaseResult | None:
        for p in self.phase_results:
            if p.phase.name == name:
                return p
        return None


# ── Verification runner ──


class VerificationRunner:
    """One-command orchestrator for all verification suites.

    Runs phases in order, collects results, produces unified
    report with artifact bundle paths.
    """

    def __init__(
        self,
        phases: list[VerificationPhase] | None = None,
        suites: list[SuiteConfig] | None = None,
        logger: StructuredTestLogger | None = None,
        timeline: EventTimeline | None = None,
        flaky_tracker: FlakyTestTracker | None = None,
    ) -> None:
        self._phases = phases or list(VERIFICATION_PHASES)
        self._suites = suites or list(MATRIX_SUITES)
        self._logger = logger or StructuredTestLogger()
        self._timeline = timeline or EventTimeline()
        self._flaky_tracker = flaky_tracker or FlakyTestTracker()
        self._matrix_runner = CIMatrixRunner(
            suites=self._suites,
            logger=self._logger,
            timeline=self._timeline,
            flaky_tracker=self._flaky_tracker,
        )
        self._phase_results: list[PhaseResult] = []
        self._started_at = time.time()
        self._run_id = f'verify-{int(self._started_at * 1000)}'

    @classmethod
    def from_defaults(cls) -> VerificationRunner:
        """Create runner with default phases and suites."""
        return cls()

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
    def run_id(self) -> str:
        return self._run_id

    @property
    def phase_results(self) -> list[PhaseResult]:
        return list(self._phase_results)

    def run_phase(
        self,
        phase: VerificationPhase,
        *,
        simulate_results: dict[str, dict[str, Any]] | None = None,
    ) -> PhaseResult:
        """Run a single verification phase."""
        start = time.monotonic()

        # Find suites for this phase
        phase_suites = [
            s for s in self._suites
            if s.suite_type in phase.suite_types and s.env == phase.env
        ]

        if not phase_suites:
            result = PhaseResult(
                phase=phase,
                status=PhaseStatus.SKIPPED,
            )
            self._phase_results.append(result)
            return result

        suite_results = []
        for config in phase_suites:
            sim = (simulate_results or {}).get(config.label)
            suite_result = self._matrix_runner.run_suite(
                config, simulate_results=sim,
            )
            suite_results.append(suite_result)

        elapsed = (time.monotonic() - start)

        # Determine phase status
        if any(r.status == RunStatus.ERROR for r in suite_results):
            status = PhaseStatus.FAILED
        elif any(r.status == RunStatus.FAILED for r in suite_results):
            status = PhaseStatus.FAILED
        elif all(r.status == RunStatus.SKIPPED for r in suite_results):
            status = PhaseStatus.SKIPPED
        else:
            status = PhaseStatus.PASSED

        result = PhaseResult(
            phase=phase,
            status=status,
            suite_results=suite_results,
            elapsed_seconds=elapsed,
        )
        self._phase_results.append(result)

        self._logger.info(
            f'Phase {phase.label}: {status.value}',
            test_name=f'phase_{phase.name}',
        )
        self._timeline.record(
            'verification_phase',
            'inbound',
            phase=phase.name,
            status=status.value,
        )
        return result

    def run_all(
        self,
        *,
        simulate_results: dict[str, dict[str, Any]] | None = None,
        stop_on_required_failure: bool = False,
        smoke_summary: dict[str, Any] | None = None,
        resilience_summary: dict[str, Any] | None = None,
        perf_summary: dict[str, Any] | None = None,
        slo_thresholds: SLOThresholds | None = None,
    ) -> VerificationReport:
        """Run all verification phases and produce report."""
        for phase in self._phases:
            result = self.run_phase(phase, simulate_results=simulate_results)

            if (stop_on_required_failure
                    and phase.required_for_go
                    and result.status == PhaseStatus.FAILED):
                # Mark remaining phases as not-run
                remaining_idx = self._phases.index(phase) + 1
                for remaining in self._phases[remaining_idx:]:
                    self._phase_results.append(PhaseResult(
                        phase=remaining,
                        status=PhaseStatus.NOT_RUN,
                    ))
                break

        matrix_report = self._matrix_runner.generate_report()

        report = VerificationReport(
            run_id=self._run_id,
            started_at=self._started_at,
            finished_at=time.time(),
            phase_results=list(self._phase_results),
            matrix_report=matrix_report,
            flaky_summary=self._flaky_tracker.to_dict(),
        )
        if smoke_summary or resilience_summary or perf_summary:
            evidence = SLOEvidence.from_sources(
                smoke_summary=smoke_summary,
                resilience_summary=resilience_summary,
                perf_summary=perf_summary,
            )
            slo = evaluate_v0_slos(
                run_id=self._run_id,
                evidence=evidence,
                thresholds=slo_thresholds,
                started_at=self._started_at,
            )
            report.slo_report = slo.to_dict()
        return report

    def save_bundle(
        self,
        report: VerificationReport,
        base_dir: Path,
    ) -> dict[str, str]:
        """Save complete artifact bundle: report, logs, timeline, manifest."""
        suite_name = 'verification'

        report_path = artifact_path(
            base_dir, suite_name, self._run_id, '.report.json',
        )
        log_path = artifact_path(
            base_dir, suite_name, self._run_id, LOG_SUFFIX,
        )
        timeline_path = artifact_path(
            base_dir, suite_name, self._run_id, TIMELINE_SUFFIX,
        )
        manifest_path = artifact_path(
            base_dir, suite_name, self._run_id, MANIFEST_SUFFIX,
        )

        # Save report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report.to_dict(), indent=2))

        # Save logs and timeline
        self._logger.save(log_path)
        self._timeline.save(timeline_path)

        # Save manifest
        manifest = TestArtifactManifest(
            test_suite=suite_name,
            run_id=self._run_id,
            started_at=self._started_at,
        )
        manifest.add_artifact('report', str(report_path), 'report')
        manifest.add_artifact('structured_log', str(log_path), 'jsonl')
        manifest.add_artifact('timeline', str(timeline_path), 'timeline')
        slo_path: Path | None = None
        if report.slo_report:
            slo_path = save_slo_report(report.slo_report, base_dir, suite_name=suite_name)
            manifest.add_artifact('slo_report', str(slo_path), 'slo')
        manifest.finish(summary={
            'verdict': report.verdict.value,
            'total_tests': report.total_tests,
            'total_passed': report.total_passed,
            'total_failed': report.total_failed,
            'slo_go_no_go': report.slo_report.get('go_no_go') if report.slo_report else '',
        })
        manifest.save(manifest_path)

        paths = {
            'report': str(report_path),
            'log': str(log_path),
            'timeline': str(timeline_path),
            'manifest': str(manifest_path),
        }
        if slo_path:
            paths['slo_report'] = str(slo_path)
        report.artifact_paths = paths
        return paths
