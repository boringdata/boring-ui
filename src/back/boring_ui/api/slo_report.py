"""SLO evidence aggregation and go/no-go reporting for V0 sandbox release."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from boring_ui.api.test_artifacts import artifact_path


class CheckStatus(Enum):
    PASS = 'pass'
    FAIL = 'fail'
    MISSING = 'missing'


@dataclass(frozen=True)
class SLOThresholds:
    """Initial V0 SLO targets (tunable as evidence matures)."""

    readiness_seconds_max: float = 5.0
    reattach_success_rate_min: float = 0.99
    reattach_window_seconds_max: float = 10.0
    ws_pty_p50_ms_max: float = 150.0
    tree_p95_multiplier_max: float = 3.0


@dataclass
class SLOEvidence:
    """Raw measured inputs used to evaluate V0 SLOs."""

    readiness_seconds: float | None = None
    reattach_success_rate: float | None = None
    reattach_window_seconds: float | None = None
    ws_pty_p50_ms: float | None = None
    tree_local_p95_ms: float | None = None
    tree_sandbox_p95_ms: float | None = None

    @property
    def tree_p95_multiplier(self) -> float | None:
        if self.tree_local_p95_ms is None or self.tree_sandbox_p95_ms is None:
            return None
        if self.tree_local_p95_ms <= 0:
            return None
        return self.tree_sandbox_p95_ms / self.tree_local_p95_ms

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.readiness_seconds is not None:
            d['readiness_seconds'] = round(self.readiness_seconds, 4)
        if self.reattach_success_rate is not None:
            d['reattach_success_rate'] = round(self.reattach_success_rate, 4)
        if self.reattach_window_seconds is not None:
            d['reattach_window_seconds'] = round(self.reattach_window_seconds, 4)
        if self.ws_pty_p50_ms is not None:
            d['ws_pty_p50_ms'] = round(self.ws_pty_p50_ms, 3)
        if self.tree_local_p95_ms is not None:
            d['tree_local_p95_ms'] = round(self.tree_local_p95_ms, 3)
        if self.tree_sandbox_p95_ms is not None:
            d['tree_sandbox_p95_ms'] = round(self.tree_sandbox_p95_ms, 3)
        if self.tree_p95_multiplier is not None:
            d['tree_p95_multiplier'] = round(self.tree_p95_multiplier, 4)
        return d

    @classmethod
    def from_sources(
        cls,
        *,
        smoke_summary: dict[str, Any] | None = None,
        resilience_summary: dict[str, Any] | None = None,
        perf_summary: dict[str, Any] | None = None,
    ) -> SLOEvidence:
        evidence = cls()

        smoke_results = (smoke_summary or {}).get('results', [])
        for result in smoke_results:
            if result.get('step') == 'readiness' and result.get('outcome') == 'pass':
                elapsed_ms = result.get('elapsed_ms')
                if isinstance(elapsed_ms, (int, float)):
                    evidence.readiness_seconds = elapsed_ms / 1000.0
                    break

        reconnect_events = 0
        reconnect_successes = 0
        max_recovery_ms = 0.0
        for result in (resilience_summary or {}).get('results', []):
            attempts = result.get('reconnect_attempts', 0)
            if isinstance(attempts, int) and attempts > 0:
                reconnect_events += 1
                if result.get('outcome') == 'recovered':
                    reconnect_successes += 1
            recovery_ms = result.get('recovery_time_ms', 0.0)
            if isinstance(recovery_ms, (int, float)):
                max_recovery_ms = max(max_recovery_ms, float(recovery_ms))

        if reconnect_events > 0:
            evidence.reattach_success_rate = reconnect_successes / reconnect_events
        if max_recovery_ms > 0:
            evidence.reattach_window_seconds = max_recovery_ms / 1000.0

        for result in (perf_summary or {}).get('results', []):
            endpoint = result.get('endpoint')
            latency = result.get('latency', {})
            if endpoint == 'pty' and isinstance(latency, dict):
                p50 = latency.get('p50')
                if isinstance(p50, (int, float)):
                    evidence.ws_pty_p50_ms = float(p50)

            if endpoint == 'tree' and isinstance(latency, dict):
                p95 = latency.get('p95')
                if not isinstance(p95, (int, float)):
                    continue
                env = str(result.get('env', '')).lower()
                if env == 'local':
                    evidence.tree_local_p95_ms = float(p95)
                elif env in {'sandbox', 'sandbox-stubbed'}:
                    evidence.tree_sandbox_p95_ms = float(p95)

        if evidence.tree_local_p95_ms is None:
            maybe_local = (perf_summary or {}).get('tree_local_p95_ms')
            if isinstance(maybe_local, (int, float)):
                evidence.tree_local_p95_ms = float(maybe_local)
        if evidence.tree_sandbox_p95_ms is None:
            maybe_sandbox = (perf_summary or {}).get('tree_sandbox_p95_ms')
            if isinstance(maybe_sandbox, (int, float)):
                evidence.tree_sandbox_p95_ms = float(maybe_sandbox)

        return evidence


@dataclass
class SLOCheck:
    name: str
    status: CheckStatus
    value: float | None
    threshold: float
    comparator: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            'name': self.name,
            'status': self.status.value,
            'threshold': self.threshold,
            'comparator': self.comparator,
            'description': self.description,
        }
        if self.value is not None:
            d['value'] = round(self.value, 4)
        return d


@dataclass
class SLOReport:
    run_id: str
    started_at: float
    finished_at: float
    thresholds: SLOThresholds
    evidence: SLOEvidence
    checks: list[SLOCheck] = field(default_factory=list)

    @property
    def go_no_go(self) -> str:
        if any(c.status in {CheckStatus.FAIL, CheckStatus.MISSING} for c in self.checks):
            return 'no-go'
        return 'go'

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'go_no_go': self.go_no_go,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'elapsed_seconds': round(self.finished_at - self.started_at, 4),
            'thresholds': {
                'readiness_seconds_max': self.thresholds.readiness_seconds_max,
                'reattach_success_rate_min': self.thresholds.reattach_success_rate_min,
                'reattach_window_seconds_max': self.thresholds.reattach_window_seconds_max,
                'ws_pty_p50_ms_max': self.thresholds.ws_pty_p50_ms_max,
                'tree_p95_multiplier_max': self.thresholds.tree_p95_multiplier_max,
            },
            'evidence': self.evidence.to_dict(),
            'checks': [c.to_dict() for c in self.checks],
        }


def _check_le(name: str, value: float | None, threshold: float, description: str) -> SLOCheck:
    if value is None:
        return SLOCheck(
            name=name,
            status=CheckStatus.MISSING,
            value=None,
            threshold=threshold,
            comparator='<=',
            description=description,
        )
    return SLOCheck(
        name=name,
        status=CheckStatus.PASS if value <= threshold else CheckStatus.FAIL,
        value=value,
        threshold=threshold,
        comparator='<=',
        description=description,
    )


def _check_ge(name: str, value: float | None, threshold: float, description: str) -> SLOCheck:
    if value is None:
        return SLOCheck(
            name=name,
            status=CheckStatus.MISSING,
            value=None,
            threshold=threshold,
            comparator='>=',
            description=description,
        )
    return SLOCheck(
        name=name,
        status=CheckStatus.PASS if value >= threshold else CheckStatus.FAIL,
        value=value,
        threshold=threshold,
        comparator='>=',
        description=description,
    )


def evaluate_v0_slos(
    *,
    run_id: str,
    evidence: SLOEvidence,
    thresholds: SLOThresholds | None = None,
    started_at: float | None = None,
) -> SLOReport:
    t = thresholds or SLOThresholds()
    started = started_at or time.time()
    checks = [
        _check_le(
            'workspace_readiness',
            evidence.readiness_seconds,
            t.readiness_seconds_max,
            'Workspace readiness check latency on warm start',
        ),
        _check_ge(
            'exec_reattach_success_rate',
            evidence.reattach_success_rate,
            t.reattach_success_rate_min,
            'Transient disconnect reattach success rate',
        ),
        _check_le(
            'exec_reattach_window_seconds',
            evidence.reattach_window_seconds,
            t.reattach_window_seconds_max,
            'Successful reattach window upper bound',
        ),
        _check_le(
            'ws_pty_p50_latency_ms',
            evidence.ws_pty_p50_ms,
            t.ws_pty_p50_ms_max,
            'PTY median input-to-output latency',
        ),
        _check_le(
            'api_tree_p95_latency_multiplier',
            evidence.tree_p95_multiplier,
            t.tree_p95_multiplier_max,
            'Sandbox /api/tree p95 vs local baseline multiplier',
        ),
    ]
    return SLOReport(
        run_id=run_id,
        started_at=started,
        finished_at=time.time(),
        thresholds=t,
        evidence=evidence,
        checks=checks,
    )


def save_slo_report(
    report: SLOReport | dict[str, Any],
    base_dir: Path,
    *,
    suite_name: str = 'verification',
) -> Path:
    run_id = report.run_id if isinstance(report, SLOReport) else report.get('run_id', 'slo')
    path = artifact_path(base_dir, suite_name, run_id, '.slo.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_dict() if isinstance(report, SLOReport) else report
    path.write_text(json.dumps(payload, indent=2))
    return path
