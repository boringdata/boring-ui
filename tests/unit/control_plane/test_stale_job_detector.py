"""Stale provisioning-job detector tests.

Bead: bd-223o.15.2 (J2)

Validates:
  - Detector identifies jobs exceeding step timeout windows
  - Stale jobs are transitioned to error with STEP_TIMEOUT code
  - Healthy (within-timeout) jobs are not modified
  - Terminal and queued jobs are skipped
  - Jobs without timestamps are skipped
  - SweepReport aggregates are correct
  - stale_by_state breakdown is accurate
  - Custom timeout overrides are respected
  - detect_only returns stale jobs without applying transitions
  - Mixed job collections are correctly categorized
  - Edge cases: zero jobs, all stale, all healthy
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from control_plane.app.operations.stale_job_detector import (
    StaleJobDetector,
    StaleJobEntry,
    SweepReport,
)
from control_plane.app.provisioning.state_machine import (
    DEFAULT_STEP_TIMEOUT_SECONDS,
    STEP_TIMEOUT_CODE,
    ProvisioningJobState,
    advance_state,
    create_queued_job,
)

UTC = timezone.utc


def _now():
    return datetime.now(UTC)


def _job_in_state(
    state: str,
    workspace_id: str = 'ws-1',
    entered_seconds_ago: int = 0,
    now: datetime | None = None,
) -> ProvisioningJobState:
    """Create a job in the given state with state_entered_at set."""
    base_now = now or _now()
    entered_at = base_now - timedelta(seconds=entered_seconds_ago)
    return ProvisioningJobState(
        workspace_id=workspace_id,
        state=state,
        attempt=1,
        state_entered_at=entered_at,
        started_at=entered_at,
    )


# =====================================================================
# 1. Basic detection
# =====================================================================


class TestBasicDetection:
    """Detector identifies stale jobs exceeding timeout."""

    def test_stale_release_resolve(self):
        now = _now()
        job = _job_in_state('release_resolve', entered_seconds_ago=20, now=now)
        detector = StaleJobDetector()
        report = detector.sweep([job], now=now)
        assert report.stale_count == 1
        assert report.healthy_count == 0
        assert report.stale[0].before.state == 'release_resolve'
        assert report.stale[0].after.state == 'error'
        assert report.stale[0].after.last_error_code == STEP_TIMEOUT_CODE

    def test_stale_creating_sandbox(self):
        now = _now()
        job = _job_in_state('creating_sandbox', entered_seconds_ago=65, now=now)
        detector = StaleJobDetector()
        report = detector.sweep([job], now=now)
        assert report.stale_count == 1
        assert report.stale[0].after.last_error_code == STEP_TIMEOUT_CODE

    def test_stale_uploading_artifact(self):
        now = _now()
        job = _job_in_state('uploading_artifact', entered_seconds_ago=65, now=now)
        detector = StaleJobDetector()
        report = detector.sweep([job], now=now)
        assert report.stale_count == 1

    def test_stale_bootstrapping(self):
        now = _now()
        job = _job_in_state('bootstrapping', entered_seconds_ago=125, now=now)
        detector = StaleJobDetector()
        report = detector.sweep([job], now=now)
        assert report.stale_count == 1

    def test_stale_health_check(self):
        now = _now()
        job = _job_in_state('health_check', entered_seconds_ago=35, now=now)
        detector = StaleJobDetector()
        report = detector.sweep([job], now=now)
        assert report.stale_count == 1


# =====================================================================
# 2. Healthy jobs not modified
# =====================================================================


class TestHealthyJobsUnchanged:
    """Jobs within timeout are classified as healthy."""

    def test_recent_release_resolve_is_healthy(self):
        now = _now()
        job = _job_in_state('release_resolve', entered_seconds_ago=5, now=now)
        detector = StaleJobDetector()
        report = detector.sweep([job], now=now)
        assert report.stale_count == 0
        assert report.healthy_count == 1

    def test_recent_bootstrapping_is_healthy(self):
        now = _now()
        job = _job_in_state('bootstrapping', entered_seconds_ago=60, now=now)
        detector = StaleJobDetector()
        report = detector.sweep([job], now=now)
        assert report.stale_count == 0
        assert report.healthy_count == 1

    def test_exactly_at_timeout_is_not_stale(self):
        """Jobs at exactly the timeout boundary are not stale (<=)."""
        now = _now()
        timeout = DEFAULT_STEP_TIMEOUT_SECONDS['release_resolve']
        job = _job_in_state(
            'release_resolve', entered_seconds_ago=timeout, now=now,
        )
        detector = StaleJobDetector()
        report = detector.sweep([job], now=now)
        assert report.stale_count == 0
        assert report.healthy_count == 1


# =====================================================================
# 3. Skip terminal and queued jobs
# =====================================================================


class TestSkipNonActive:
    """Terminal and queued jobs are skipped without evaluation."""

    def test_ready_job_skipped(self):
        now = _now()
        job = ProvisioningJobState(
            workspace_id='ws-1', state='ready',
            state_entered_at=now - timedelta(seconds=1000),
            started_at=now - timedelta(seconds=2000),
            finished_at=now - timedelta(seconds=1000),
        )
        report = StaleJobDetector().sweep([job], now=now)
        assert len(report.skipped) == 1
        assert report.stale_count == 0

    def test_error_job_skipped(self):
        now = _now()
        job = ProvisioningJobState(
            workspace_id='ws-1', state='error',
            state_entered_at=now - timedelta(seconds=500),
            started_at=now - timedelta(seconds=1000),
            finished_at=now - timedelta(seconds=500),
            last_error_code='SOME_ERROR',
        )
        report = StaleJobDetector().sweep([job], now=now)
        assert len(report.skipped) == 1
        assert report.stale_count == 0

    def test_queued_job_skipped(self):
        now = _now()
        job = _job_in_state('queued', entered_seconds_ago=1000, now=now)
        report = StaleJobDetector().sweep([job], now=now)
        assert len(report.skipped) == 1
        assert report.stale_count == 0

    def test_no_timestamp_skipped(self):
        job = ProvisioningJobState(
            workspace_id='ws-1',
            state='creating_sandbox',
            state_entered_at=None,
        )
        report = StaleJobDetector().sweep([job], now=_now())
        assert len(report.skipped) == 1


# =====================================================================
# 4. SweepReport properties
# =====================================================================


class TestSweepReportProperties:
    """Report aggregates are correct."""

    def test_total_scanned(self):
        now = _now()
        jobs = [
            _job_in_state('release_resolve', entered_seconds_ago=20, now=now),
            _job_in_state('bootstrapping', entered_seconds_ago=10, now=now),
            _job_in_state('queued', entered_seconds_ago=100, now=now),
        ]
        report = StaleJobDetector().sweep(jobs, now=now)
        assert report.total_scanned == 3

    def test_sweep_ts_matches(self):
        now = _now()
        report = StaleJobDetector().sweep([], now=now)
        assert report.sweep_ts == now

    def test_stale_by_state_breakdown(self):
        now = _now()
        jobs = [
            _job_in_state(
                'release_resolve', workspace_id='ws-1',
                entered_seconds_ago=20, now=now,
            ),
            _job_in_state(
                'release_resolve', workspace_id='ws-2',
                entered_seconds_ago=20, now=now,
            ),
            _job_in_state(
                'health_check', workspace_id='ws-3',
                entered_seconds_ago=35, now=now,
            ),
        ]
        report = StaleJobDetector().sweep(jobs, now=now)
        assert report.stale_by_state == {
            'release_resolve': 2,
            'health_check': 1,
        }


# =====================================================================
# 5. Custom timeout overrides
# =====================================================================


class TestCustomTimeouts:
    """Detector respects custom step_timeouts."""

    def test_shorter_timeout_makes_more_jobs_stale(self):
        now = _now()
        job = _job_in_state(
            'bootstrapping', entered_seconds_ago=30, now=now,
        )
        # Default bootstrapping timeout is 120s, so 30s is healthy.
        default_report = StaleJobDetector().sweep([job], now=now)
        assert default_report.stale_count == 0

        # With custom 10s timeout, 30s is stale.
        custom = StaleJobDetector(step_timeouts={'bootstrapping': 10})
        custom_report = custom.sweep([job], now=now)
        assert custom_report.stale_count == 1

    def test_longer_timeout_keeps_jobs_healthy(self):
        now = _now()
        job = _job_in_state(
            'release_resolve', entered_seconds_ago=20, now=now,
        )
        # Default is 15s, so 20s is stale.
        default = StaleJobDetector().sweep([job], now=now)
        assert default.stale_count == 1

        # With 30s timeout, 20s is healthy.
        custom = StaleJobDetector(step_timeouts={'release_resolve': 30})
        custom_report = custom.sweep([job], now=now)
        assert custom_report.stale_count == 0


# =====================================================================
# 6. detect_only (dry-run)
# =====================================================================


class TestDetectOnly:
    """detect_only returns original stale jobs without transitions."""

    def test_returns_original_jobs(self):
        now = _now()
        stale_job = _job_in_state(
            'release_resolve', entered_seconds_ago=20, now=now,
        )
        healthy_job = _job_in_state(
            'bootstrapping', entered_seconds_ago=10, now=now,
        )
        result = StaleJobDetector().detect_only(
            [stale_job, healthy_job], now=now,
        )
        assert len(result) == 1
        assert result[0] is stale_job
        assert result[0].state == 'release_resolve'  # Not transitioned.


# =====================================================================
# 7. Mixed job collections
# =====================================================================


class TestMixedCollections:
    """Collections with stale, healthy, and skipped jobs."""

    def test_mixed_sweep(self):
        now = _now()
        jobs = [
            _job_in_state('release_resolve', 'ws-stale', 20, now),
            _job_in_state('bootstrapping', 'ws-healthy', 10, now),
            _job_in_state('health_check', 'ws-stale2', 35, now),
            ProvisioningJobState(
                workspace_id='ws-ready', state='ready',
                state_entered_at=now, started_at=now, finished_at=now,
            ),
            ProvisioningJobState(
                workspace_id='ws-queued', state='queued',
                state_entered_at=now, started_at=now,
            ),
        ]
        report = StaleJobDetector().sweep(jobs, now=now)
        assert report.stale_count == 2
        assert report.healthy_count == 1
        assert len(report.skipped) == 2
        assert report.total_scanned == 5

        stale_ws = {e.before.workspace_id for e in report.stale}
        assert stale_ws == {'ws-stale', 'ws-stale2'}

        healthy_ws = {j.workspace_id for j in report.healthy}
        assert healthy_ws == {'ws-healthy'}


# =====================================================================
# 8. Edge cases
# =====================================================================


class TestEdgeCases:
    """Edge cases: empty, all stale, all healthy."""

    def test_empty_collection(self):
        report = StaleJobDetector().sweep([], now=_now())
        assert report.stale_count == 0
        assert report.healthy_count == 0
        assert report.total_scanned == 0
        assert report.stale_by_state == {}

    def test_all_stale(self):
        now = _now()
        jobs = [
            _job_in_state('release_resolve', f'ws-{i}', 20, now)
            for i in range(5)
        ]
        report = StaleJobDetector().sweep(jobs, now=now)
        assert report.stale_count == 5
        assert report.healthy_count == 0

    def test_all_healthy(self):
        now = _now()
        jobs = [
            _job_in_state('bootstrapping', f'ws-{i}', 10, now)
            for i in range(5)
        ]
        report = StaleJobDetector().sweep(jobs, now=now)
        assert report.stale_count == 0
        assert report.healthy_count == 5

    def test_all_terminal(self):
        now = _now()
        jobs = [
            ProvisioningJobState(
                workspace_id=f'ws-{i}', state='ready',
                state_entered_at=now, started_at=now, finished_at=now,
            )
            for i in range(3)
        ]
        report = StaleJobDetector().sweep(jobs, now=now)
        assert report.stale_count == 0
        assert report.healthy_count == 0
        assert len(report.skipped) == 3


# =====================================================================
# 9. Error code visibility (J1 alert integration)
# =====================================================================


class TestErrorCodeVisibility:
    """Stale jobs produce STEP_TIMEOUT error code for alert grouping."""

    def test_error_code_is_step_timeout(self):
        now = _now()
        job = _job_in_state('creating_sandbox', entered_seconds_ago=65, now=now)
        report = StaleJobDetector().sweep([job], now=now)
        entry = report.stale[0]
        assert entry.after.last_error_code == STEP_TIMEOUT_CODE

    def test_error_detail_includes_step_name(self):
        now = _now()
        job = _job_in_state('health_check', entered_seconds_ago=35, now=now)
        report = StaleJobDetector().sweep([job], now=now)
        detail = report.stale[0].after.last_error_detail
        assert 'health_check' in detail

    def test_error_detail_includes_elapsed_time(self):
        now = _now()
        job = _job_in_state('release_resolve', entered_seconds_ago=20, now=now)
        report = StaleJobDetector().sweep([job], now=now)
        detail = report.stale[0].after.last_error_detail
        assert '20s' in detail
        assert '15s' in detail  # Timeout threshold.

    def test_elapsed_seconds_tracked(self):
        now = _now()
        job = _job_in_state('release_resolve', entered_seconds_ago=25, now=now)
        report = StaleJobDetector().sweep([job], now=now)
        assert report.stale[0].elapsed_seconds == pytest.approx(25.0, abs=1)
        assert report.stale[0].timeout_seconds == 15


# =====================================================================
# 10. StaleJobEntry and SweepReport are frozen
# =====================================================================


class TestDataclassInvariants:
    """Detector results are immutable."""

    def test_stale_entry_frozen(self):
        now = _now()
        job = _job_in_state('release_resolve', entered_seconds_ago=20, now=now)
        report = StaleJobDetector().sweep([job], now=now)
        with pytest.raises(AttributeError):
            report.stale[0].elapsed_seconds = 0

    def test_sweep_report_frozen(self):
        report = StaleJobDetector().sweep([], now=_now())
        with pytest.raises(AttributeError):
            report.sweep_ts = _now()
