"""Unit tests for V0 SLO evidence aggregation and go/no-go reporting."""
import json
from pathlib import Path

from boring_ui.api.slo_report import (
    CheckStatus,
    SLOEvidence,
    SLOThresholds,
    evaluate_v0_slos,
    save_slo_report,
)


def test_evidence_from_sources_extracts_metrics():
    smoke_summary = {
        'results': [
            {'step': 'readiness', 'outcome': 'pass', 'elapsed_ms': 1250.0},
        ]
    }
    resilience_summary = {
        'results': [
            {'reconnect_attempts': 1, 'outcome': 'recovered', 'recovery_time_ms': 500.0},
            {'reconnect_attempts': 1, 'outcome': 'recovered', 'recovery_time_ms': 700.0},
        ]
    }
    perf_summary = {
        'results': [
            {'endpoint': 'pty', 'latency': {'p50': 120.0}},
        ],
        'tree_local_p95_ms': 40.0,
        'tree_sandbox_p95_ms': 80.0,
    }

    evidence = SLOEvidence.from_sources(
        smoke_summary=smoke_summary,
        resilience_summary=resilience_summary,
        perf_summary=perf_summary,
    )

    assert evidence.readiness_seconds == 1.25
    assert evidence.reattach_success_rate == 1.0
    assert evidence.reattach_window_seconds == 0.7
    assert evidence.ws_pty_p50_ms == 120.0
    assert evidence.tree_p95_multiplier == 2.0


def test_evaluate_v0_slos_go():
    evidence = SLOEvidence(
        readiness_seconds=1.0,
        reattach_success_rate=1.0,
        reattach_window_seconds=1.0,
        ws_pty_p50_ms=40.0,
        tree_local_p95_ms=30.0,
        tree_sandbox_p95_ms=60.0,
    )
    report = evaluate_v0_slos(run_id='verify-1', evidence=evidence)

    assert report.go_no_go == 'go'
    assert all(c.status == CheckStatus.PASS for c in report.checks)


def test_evaluate_v0_slos_missing_is_no_go():
    report = evaluate_v0_slos(run_id='verify-2', evidence=SLOEvidence())
    assert report.go_no_go == 'no-go'
    assert any(c.status == CheckStatus.MISSING for c in report.checks)


def test_evaluate_v0_slos_threshold_failures():
    evidence = SLOEvidence(
        readiness_seconds=9.0,
        reattach_success_rate=0.5,
        reattach_window_seconds=30.0,
        ws_pty_p50_ms=250.0,
        tree_local_p95_ms=20.0,
        tree_sandbox_p95_ms=100.0,
    )
    thresholds = SLOThresholds(
        readiness_seconds_max=5.0,
        reattach_success_rate_min=0.99,
        reattach_window_seconds_max=10.0,
        ws_pty_p50_ms_max=150.0,
        tree_p95_multiplier_max=3.0,
    )
    report = evaluate_v0_slos(
        run_id='verify-3',
        evidence=evidence,
        thresholds=thresholds,
    )

    assert report.go_no_go == 'no-go'
    assert any(c.status == CheckStatus.FAIL for c in report.checks)


def test_save_slo_report_writes_json(tmp_path):
    evidence = SLOEvidence(
        readiness_seconds=1.0,
        reattach_success_rate=1.0,
        reattach_window_seconds=1.0,
        ws_pty_p50_ms=40.0,
        tree_local_p95_ms=20.0,
        tree_sandbox_p95_ms=30.0,
    )
    report = evaluate_v0_slos(run_id='verify-4', evidence=evidence)
    path = save_slo_report(report, tmp_path)

    assert path.exists()
    data = json.loads(Path(path).read_text())
    assert data['run_id'] == 'verify-4'
    assert data['go_no_go'] == 'go'
