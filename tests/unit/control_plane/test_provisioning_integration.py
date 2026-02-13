"""Comprehensive provisioning integration tests.

Bead: bd-r6at (D6)

Cross-module integration tests covering the full provisioning lifecycle:
  - State machine transitions through all 7 states to ready
  - Multi-retry recovery (error → retry → re-advance → ready)
  - Per-step timeout detection for all 5 active steps
  - Error transitions from every active state
  - Artifact store + release contract + state machine integration
  - Stale job detector sweep across mixed workloads
  - State invariant verification (legal vs illegal transitions)
  - Multi-workspace isolation (independent provisioning jobs)
  - Observability compatibility (error codes match metric labels)
  - Provisioning test fixtures for downstream D3-D5 tests
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from control_plane.app.provisioning.state_machine import (
    ACTIVE_STATES,
    ALLOWED_TRANSITIONS,
    DEFAULT_STEP_TIMEOUT_SECONDS,
    PROVISIONING_SEQUENCE,
    STEP_TIMEOUT_CODE,
    TERMINAL_STATES,
    InvalidStateTransition,
    ProvisioningJobState,
    advance_state,
    apply_step_timeout,
    create_queued_job,
    retry_from_error,
    transition_to_error,
)
from control_plane.app.provisioning.release_contract import (
    RELEASE_UNAVAILABLE_CODE,
    ProvisioningTarget,
    ReleaseUnavailableError,
    build_sandbox_name,
    resolve_provisioning_target,
)
from control_plane.app.provisioning.artifacts import (
    BUNDLE_FILENAME,
    MANIFEST_FILENAME,
    FileSystemArtifactStore,
    build_manifest,
    compute_sha256,
)
from control_plane.app.operations.stale_job_detector import (
    StaleJobDetector,
    StaleJobEntry,
    SweepReport,
)


# ── Test helpers ────────────────────────────────────────────────────


def _t(seconds: int = 0) -> datetime:
    """Timezone-aware timestamp helper."""
    return datetime(2026, 2, 13, 12, 0, 0, tzinfo=UTC) + timedelta(
        seconds=seconds
    )


def _advance_to_state(
    workspace_id: str,
    target_state: str,
    start_seconds: int = 0,
) -> ProvisioningJobState:
    """Advance a job from queued to the given target state."""
    job = create_queued_job(workspace_id=workspace_id, now=_t(start_seconds))
    seq_index = PROVISIONING_SEQUENCE.index(target_state)
    for i in range(seq_index):
        job = advance_state(job, now=_t(start_seconds + i + 1))
    assert job.state == target_state
    return job


def _advance_to_ready(
    workspace_id: str,
    start_seconds: int = 0,
) -> ProvisioningJobState:
    """Advance a job all the way from queued to ready."""
    return _advance_to_state(workspace_id, 'ready', start_seconds)


def _publish_test_release(
    store: FileSystemArtifactStore,
    bundle_path: Path,
    app_id: str = 'test-app',
    release_id: str = 'v1',
) -> None:
    """Publish a test release into the artifact store."""
    manifest = build_manifest(
        app_id=app_id,
        release_id=release_id,
        bundle_path=bundle_path,
    )
    store.publish(manifest, bundle_path)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def artifact_store(tmp_path: Path) -> FileSystemArtifactStore:
    """Artifact store in a temp directory."""
    return FileSystemArtifactStore(tmp_path)


@pytest.fixture
def bundle_file(tmp_path: Path) -> Path:
    """Sample bundle file with deterministic content."""
    p = tmp_path / 'test_bundle.tar.gz'
    p.write_bytes(b'deterministic-test-bundle-content-for-d6')
    return p


@pytest.fixture
def stale_detector() -> StaleJobDetector:
    """StaleJobDetector with default timeouts."""
    return StaleJobDetector()


# =====================================================================
# 1. Full lifecycle simulation — queued through ready
# =====================================================================


class TestFullLifecycle:
    """Verify a job can advance through all 7 provisioning states."""

    def test_full_sequence_reaches_ready(self):
        """queued → release_resolve → ... → ready."""
        job = create_queued_job(workspace_id='ws-lifecycle', now=_t(0))
        for i, expected_state in enumerate(PROVISIONING_SEQUENCE[1:], 1):
            job = advance_state(job, now=_t(i))
            assert job.state == expected_state

        assert job.state == 'ready'
        assert job.finished_at is not None
        assert job.attempt == 1

    def test_state_entered_at_updates_each_step(self):
        """Each advance updates state_entered_at."""
        job = create_queued_job(workspace_id='ws-ts', now=_t(0))
        for i in range(1, 7):
            job = advance_state(job, now=_t(i * 10))
            assert job.state_entered_at == _t(i * 10)

    def test_started_at_persists_from_creation(self):
        """started_at is set at queued and never overwritten."""
        job = create_queued_job(workspace_id='ws-started', now=_t(100))
        assert job.started_at == _t(100)

        for i in range(1, 7):
            job = advance_state(job, now=_t(100 + i))
        assert job.started_at == _t(100)

    def test_finished_at_only_set_at_terminal(self):
        """finished_at is None until ready or error."""
        job = create_queued_job(workspace_id='ws-fin', now=_t(0))
        for i in range(1, 6):
            job = advance_state(job, now=_t(i))
            assert job.finished_at is None

        job = advance_state(job, now=_t(6))
        assert job.state == 'ready'
        assert job.finished_at == _t(6)

    def test_workspace_id_preserved_throughout(self):
        """workspace_id never changes during transitions."""
        job = create_queued_job(workspace_id='ws-preserve', now=_t(0))
        for i in range(1, 7):
            job = advance_state(job, now=_t(i))
            assert job.workspace_id == 'ws-preserve'


# =====================================================================
# 2. Multi-retry recovery
# =====================================================================


class TestMultiRetryRecovery:
    """Verify error → retry → advance cycle works repeatedly."""

    def test_single_retry_to_ready(self):
        """error → retry → queued → ... → ready."""
        job = _advance_to_state('ws-retry1', 'release_resolve', 0)
        job = transition_to_error(
            job, now=_t(10), error_code='transient', error_detail='temp fail',
        )
        assert job.state == 'error'
        assert job.attempt == 1

        job = retry_from_error(job, now=_t(20))
        assert job.state == 'queued'
        assert job.attempt == 2
        assert job.last_error_code is None

        for i in range(1, 7):
            job = advance_state(job, now=_t(20 + i))

        assert job.state == 'ready'
        assert job.attempt == 2

    def test_triple_retry_to_ready(self):
        """Three failures before success: attempt should be 4."""
        job = create_queued_job(workspace_id='ws-retry3', now=_t(0))
        t = 0

        for retry_num in range(3):
            t += 1
            job = advance_state(job, now=_t(t))  # → release_resolve
            t += 1
            job = transition_to_error(
                job, now=_t(t),
                error_code=f'fail_{retry_num}',
                error_detail=f'failure #{retry_num}',
            )
            t += 1
            job = retry_from_error(job, now=_t(t))
            assert job.attempt == retry_num + 2

        # Fourth attempt succeeds.
        for _ in range(6):
            t += 1
            job = advance_state(job, now=_t(t))

        assert job.state == 'ready'
        assert job.attempt == 4

    def test_retry_clears_error_fields(self):
        """Error code and detail are cleared on retry."""
        job = _advance_to_state('ws-clear', 'creating_sandbox', 0)
        job = transition_to_error(
            job, now=_t(10),
            error_code='ARTIFACT_CHECKSUM_MISMATCH',
            error_detail='bundle hash mismatch',
        )
        assert job.last_error_code == 'ARTIFACT_CHECKSUM_MISMATCH'
        assert job.last_error_detail == 'bundle hash mismatch'

        retried = retry_from_error(job, now=_t(20))
        assert retried.last_error_code is None
        assert retried.last_error_detail is None

    def test_retry_from_non_error_raises(self):
        """Cannot retry from a non-error state."""
        job = _advance_to_state('ws-invalid-retry', 'bootstrapping', 0)
        with pytest.raises(InvalidStateTransition):
            retry_from_error(job, now=_t(100))

    def test_retry_from_ready_raises(self):
        """Cannot retry from ready."""
        job = _advance_to_ready('ws-ready-retry', 0)
        with pytest.raises(InvalidStateTransition):
            retry_from_error(job, now=_t(100))


# =====================================================================
# 3. Per-step timeout coverage
# =====================================================================


class TestPerStepTimeouts:
    """Verify timeout detection for every timed active state."""

    @pytest.mark.parametrize('step', [
        'release_resolve',
        'creating_sandbox',
        'uploading_artifact',
        'bootstrapping',
        'health_check',
    ])
    def test_step_timeout_transitions_to_error(self, step: str):
        """Each active step times out with STEP_TIMEOUT code."""
        job = _advance_to_state('ws-timeout', step, 0)
        timeout_secs = DEFAULT_STEP_TIMEOUT_SECONDS[step]
        seq_idx = PROVISIONING_SEQUENCE.index(step)

        # now must exceed state_entered_at + timeout
        result = apply_step_timeout(job, now=_t(seq_idx + timeout_secs + 1))
        assert result.state == 'error'
        assert result.last_error_code == STEP_TIMEOUT_CODE
        assert step in (result.last_error_detail or '')

    @pytest.mark.parametrize('step', [
        'release_resolve',
        'creating_sandbox',
        'uploading_artifact',
        'bootstrapping',
        'health_check',
    ])
    def test_step_within_timeout_stays_healthy(self, step: str):
        """No timeout when within the threshold."""
        job = _advance_to_state('ws-healthy', step, 0)
        timeout_secs = DEFAULT_STEP_TIMEOUT_SECONDS[step]
        seq_idx = PROVISIONING_SEQUENCE.index(step)

        result = apply_step_timeout(job, now=_t(seq_idx + timeout_secs - 1))
        assert result.state == step

    @pytest.mark.parametrize('step', [
        'release_resolve',
        'creating_sandbox',
        'uploading_artifact',
        'bootstrapping',
        'health_check',
    ])
    def test_step_at_exact_timeout_boundary_is_healthy(self, step: str):
        """At exactly timeout seconds, no transition occurs."""
        job = _advance_to_state('ws-boundary', step, 0)
        timeout_secs = DEFAULT_STEP_TIMEOUT_SECONDS[step]
        seq_idx = PROVISIONING_SEQUENCE.index(step)

        result = apply_step_timeout(
            job, now=_t(seq_idx + timeout_secs),
        )
        assert result.state == step

    def test_timeout_noop_for_queued(self):
        """Queued state is not subject to timeout."""
        job = create_queued_job(workspace_id='ws-q', now=_t(0))
        result = apply_step_timeout(job, now=_t(9999))
        assert result.state == 'queued'

    def test_timeout_noop_for_ready(self):
        """Ready state is not subject to timeout."""
        job = _advance_to_ready('ws-rdy', 0)
        result = apply_step_timeout(job, now=_t(9999))
        assert result.state == 'ready'

    def test_timeout_noop_for_error(self):
        """Error state is not subject to timeout."""
        job = _advance_to_state('ws-err', 'release_resolve', 0)
        job = transition_to_error(
            job, now=_t(5), error_code='x', error_detail='x',
        )
        result = apply_step_timeout(job, now=_t(9999))
        assert result.state == 'error'

    def test_timeout_recovery_cycle(self):
        """timeout → error → retry → advance past timed-out step → ready."""
        job = _advance_to_state('ws-timeout-recover', 'bootstrapping', 0)
        timeout_secs = DEFAULT_STEP_TIMEOUT_SECONDS['bootstrapping']

        timed_out = apply_step_timeout(
            job, now=_t(100 + timeout_secs + 1),
        )
        assert timed_out.state == 'error'
        assert timed_out.last_error_code == STEP_TIMEOUT_CODE

        retried = retry_from_error(timed_out, now=_t(200))
        assert retried.state == 'queued'
        assert retried.attempt == 2

        # Advance all the way to ready.
        t = 200
        for _ in range(6):
            t += 1
            retried = advance_state(retried, now=_t(t))
        assert retried.state == 'ready'


# =====================================================================
# 4. Error from every active state
# =====================================================================


class TestErrorFromEveryState:
    """Verify error transition is valid from all non-queued active states."""

    @pytest.mark.parametrize('step', [
        'release_resolve',
        'creating_sandbox',
        'uploading_artifact',
        'bootstrapping',
        'health_check',
    ])
    def test_error_from_active_state(self, step: str):
        """Each active step can transition to error."""
        job = _advance_to_state('ws-err', step, 0)
        errored = transition_to_error(
            job, now=_t(50),
            error_code='test_error',
            error_detail=f'error during {step}',
        )
        assert errored.state == 'error'
        assert errored.last_error_code == 'test_error'
        assert errored.finished_at == _t(50)

    def test_error_from_queued_is_invalid(self):
        """Queued cannot directly transition to error."""
        job = create_queued_job(workspace_id='ws-q-err', now=_t(0))
        with pytest.raises(InvalidStateTransition):
            transition_to_error(
                job, now=_t(1), error_code='x', error_detail='x',
            )

    def test_error_from_ready_is_invalid(self):
        """Ready cannot transition to error."""
        job = _advance_to_ready('ws-rdy-err', 0)
        with pytest.raises(InvalidStateTransition):
            transition_to_error(
                job, now=_t(50), error_code='x', error_detail='x',
            )

    def test_error_from_error_is_invalid(self):
        """Error cannot transition to error again."""
        job = _advance_to_state('ws-err-err', 'release_resolve', 0)
        job = transition_to_error(
            job, now=_t(5), error_code='first', error_detail='first',
        )
        with pytest.raises(InvalidStateTransition):
            transition_to_error(
                job, now=_t(10), error_code='second', error_detail='second',
            )


# =====================================================================
# 5. State invariant verification
# =====================================================================


class TestStateInvariants:
    """Verify structural invariants of the state machine."""

    def test_all_states_are_in_sequence_or_error(self):
        """Every state in ALLOWED_TRANSITIONS is either in sequence or 'error'."""
        all_states = set(PROVISIONING_SEQUENCE) | {'error'}
        assert set(ALLOWED_TRANSITIONS.keys()) == all_states

    def test_terminal_states_have_no_forward_advance(self):
        """Terminal states (ready, error) don't allow advance_state."""
        for state in TERMINAL_STATES:
            if state == 'error':
                # Error allows retry to queued, not advance.
                assert 'queued' in ALLOWED_TRANSITIONS['error']
            elif state == 'ready':
                assert len(ALLOWED_TRANSITIONS['ready']) == 0

    def test_active_states_union_terminal_covers_all(self):
        """ACTIVE_STATES ∪ TERMINAL_STATES = all states."""
        all_states = set(PROVISIONING_SEQUENCE) | {'error'}
        assert ACTIVE_STATES | TERMINAL_STATES == all_states

    def test_sequence_is_seven_steps(self):
        """Canonical provisioning has exactly 7 steps."""
        assert len(PROVISIONING_SEQUENCE) == 7

    def test_sequence_starts_queued_ends_ready(self):
        assert PROVISIONING_SEQUENCE[0] == 'queued'
        assert PROVISIONING_SEQUENCE[-1] == 'ready'

    def test_every_active_step_except_queued_can_error(self):
        """All active states except queued can transition to error."""
        for state in ACTIVE_STATES - {'queued'}:
            assert 'error' in ALLOWED_TRANSITIONS[state]

    def test_every_non_terminal_has_exactly_one_forward_and_maybe_error(self):
        """Each state in sequence (except ready/error) has 1 forward + error."""
        for i, state in enumerate(PROVISIONING_SEQUENCE[:-1]):
            allowed = ALLOWED_TRANSITIONS[state]
            next_state = PROVISIONING_SEQUENCE[i + 1]
            assert next_state in allowed
            if state != 'queued':
                assert 'error' in allowed

    def test_default_timeouts_cover_all_timed_states(self):
        """Every active state except queued has a defined timeout."""
        timed_states = ACTIVE_STATES - {'queued'}
        assert set(DEFAULT_STEP_TIMEOUT_SECONDS.keys()) == timed_states


# =====================================================================
# 6. Cross-module integration: artifacts + release + state machine
# =====================================================================


class TestCrossModuleIntegration:
    """End-to-end: resolve target from artifact store, then run state machine."""

    def test_resolve_target_then_advance_to_ready(
        self,
        artifact_store: FileSystemArtifactStore,
        bundle_file: Path,
    ):
        """Resolve a provisioning target from real artifacts, then run FSM."""
        _publish_test_release(artifact_store, bundle_file, 'my-app', 'v2.0')

        target = resolve_provisioning_target(
            app_id='my-app',
            workspace_id='ws-123',
            env='production',
            requested_release_id='v2.0',
            default_release_id=None,
            artifact_lookup=artifact_store,
        )
        assert target.app_id == 'my-app'
        assert target.release_id == 'v2.0'
        assert target.sandbox_name == 'sbx-my-app-ws-123-production'
        assert target.bundle_sha256 == compute_sha256(bundle_file)

        # Now run FSM using resolved target.
        job = create_queued_job(
            workspace_id=target.workspace_id, now=_t(0),
        )
        for i in range(1, 7):
            job = advance_state(job, now=_t(i))
        assert job.state == 'ready'

    def test_missing_artifact_blocks_provisioning(
        self, artifact_store: FileSystemArtifactStore,
    ):
        """Missing artifacts prevent creating a provisioning job."""
        with pytest.raises(ReleaseUnavailableError) as exc_info:
            resolve_provisioning_target(
                app_id='my-app',
                workspace_id='ws-123',
                env='prod',
                requested_release_id='v-missing',
                default_release_id=None,
                artifact_lookup=artifact_store,
            )
        assert exc_info.value.reason == 'artifacts_not_found'

    def test_corrupted_bundle_detected_before_provisioning(
        self,
        artifact_store: FileSystemArtifactStore,
        bundle_file: Path,
    ):
        """Corrupted bundle fails verify even after target resolution."""
        _publish_test_release(artifact_store, bundle_file, 'my-app', 'v1')

        # Resolve target succeeds (manifest exists).
        target = resolve_provisioning_target(
            app_id='my-app',
            workspace_id='ws-123',
            env='prod',
            requested_release_id='v1',
            default_release_id=None,
            artifact_lookup=artifact_store,
        )
        assert target.bundle_sha256

        # Corrupt the on-disk bundle.
        bp = artifact_store.bundle_path('my-app', 'v1')
        assert bp is not None
        bp.write_bytes(b'corrupted-bundle')

        # Verify detects corruption.
        assert artifact_store.verify_bundle('my-app', 'v1') is False

    def test_multiple_releases_isolation(
        self,
        artifact_store: FileSystemArtifactStore,
        bundle_file: Path,
        tmp_path: Path,
    ):
        """Multiple releases for the same app are independently resolvable."""
        _publish_test_release(artifact_store, bundle_file, 'my-app', 'v1')

        bundle_v2 = tmp_path / 'v2_bundle.tar.gz'
        bundle_v2.write_bytes(b'different-v2-bundle-content')
        _publish_test_release(artifact_store, bundle_v2, 'my-app', 'v2')

        t1 = resolve_provisioning_target(
            app_id='my-app', workspace_id='ws-1', env='prod',
            requested_release_id='v1', default_release_id=None,
            artifact_lookup=artifact_store,
        )
        t2 = resolve_provisioning_target(
            app_id='my-app', workspace_id='ws-1', env='prod',
            requested_release_id='v2', default_release_id=None,
            artifact_lookup=artifact_store,
        )
        assert t1.release_id == 'v1'
        assert t2.release_id == 'v2'
        assert t1.bundle_sha256 != t2.bundle_sha256


# =====================================================================
# 7. Stale job detector integration
# =====================================================================


class TestStaleJobDetectorIntegration:
    """StaleJobDetector across mixed provisioning workloads."""

    def test_sweep_detects_stale_jobs(self, stale_detector: StaleJobDetector):
        """Stale jobs in various states are detected."""
        # Start healthy job recently so it's within timeout.
        healthy = _advance_to_state('ws-ok', 'creating_sandbox', 1000)
        # Start stale job long ago so it exceeds timeout.
        stale = _advance_to_state('ws-stale', 'bootstrapping', 0)

        # Pick a time where stale is timed out but healthy is not.
        # healthy: creating_sandbox entered at _t(1002), timeout=60s
        # stale: bootstrapping entered at _t(4), timeout=120s
        sweep_time = 1000 + 2 + 30  # 30s into healthy's creating_sandbox
        report = stale_detector.sweep(
            [healthy, stale],
            now=_t(sweep_time),
        )

        assert report.stale_count == 1
        assert report.stale[0].before.workspace_id == 'ws-stale'
        assert report.stale[0].after.state == 'error'
        assert report.stale[0].after.last_error_code == STEP_TIMEOUT_CODE

    def test_sweep_skips_terminal_and_queued(
        self, stale_detector: StaleJobDetector,
    ):
        """Terminal and queued jobs are skipped."""
        queued = create_queued_job(workspace_id='ws-q', now=_t(0))
        ready = _advance_to_ready('ws-r', 0)
        errored = _advance_to_state('ws-e', 'release_resolve', 0)
        errored = transition_to_error(
            errored, now=_t(5), error_code='x', error_detail='x',
        )

        report = stale_detector.sweep(
            [queued, ready, errored],
            now=_t(9999),
        )
        assert report.stale_count == 0
        assert len(report.skipped) == 3

    def test_sweep_healthy_jobs_stay_healthy(
        self, stale_detector: StaleJobDetector,
    ):
        """Jobs within timeout appear in healthy list."""
        job = _advance_to_state('ws-fresh', 'creating_sandbox', 100)
        timeout = DEFAULT_STEP_TIMEOUT_SECONDS['creating_sandbox']

        report = stale_detector.sweep(
            [job], now=_t(100 + 2 + timeout - 5),
        )
        assert report.healthy_count == 1
        assert report.stale_count == 0

    def test_sweep_report_stale_by_state(
        self, stale_detector: StaleJobDetector,
    ):
        """stale_by_state groups stale jobs by original state."""
        stale_boot = _advance_to_state('ws-b1', 'bootstrapping', 0)
        stale_boot2 = _advance_to_state('ws-b2', 'bootstrapping', 0)
        stale_hc = _advance_to_state('ws-hc', 'health_check', 0)

        report = stale_detector.sweep(
            [stale_boot, stale_boot2, stale_hc],
            now=_t(9999),
        )
        by_state = report.stale_by_state
        assert by_state.get('bootstrapping') == 2
        assert by_state.get('health_check') == 1

    def test_sweep_report_total_scanned(
        self, stale_detector: StaleJobDetector,
    ):
        """total_scanned includes stale + healthy + skipped."""
        queued = create_queued_job(workspace_id='ws-q', now=_t(0))
        healthy = _advance_to_state('ws-h', 'creating_sandbox', 100)
        stale = _advance_to_state('ws-s', 'bootstrapping', 0)

        report = stale_detector.sweep(
            [queued, healthy, stale],
            now=_t(9999),
        )
        assert report.total_scanned == 3

    def test_detect_only_returns_original_states(
        self, stale_detector: StaleJobDetector,
    ):
        """detect_only returns stale jobs without mutating them."""
        stale = _advance_to_state('ws-stale', 'health_check', 0)
        result = stale_detector.detect_only([stale], now=_t(9999))
        assert len(result) == 1
        assert result[0].state == 'health_check'  # Original, not error.

    def test_custom_timeouts(self):
        """Custom timeouts override defaults."""
        custom = {'releasing_sandbox': 5, 'health_check': 2}
        detector = StaleJobDetector(step_timeouts=custom)

        job = _advance_to_state('ws-custom', 'health_check', 0)
        seq_idx = PROVISIONING_SEQUENCE.index('health_check')
        report = detector.sweep([job], now=_t(seq_idx + 3))
        assert report.stale_count == 1


# =====================================================================
# 8. Multi-workspace isolation
# =====================================================================


class TestMultiWorkspaceIsolation:
    """Provisioning jobs for different workspaces are independent."""

    def test_independent_advancement(self):
        """Two workspaces advance independently."""
        ws1 = create_queued_job(workspace_id='ws-1', now=_t(0))
        ws2 = create_queued_job(workspace_id='ws-2', now=_t(0))

        ws1 = advance_state(ws1, now=_t(1))
        assert ws1.state == 'release_resolve'
        assert ws2.state == 'queued'

        ws2 = advance_state(ws2, now=_t(2))
        ws2 = advance_state(ws2, now=_t(3))
        assert ws2.state == 'creating_sandbox'
        assert ws1.state == 'release_resolve'

    def test_error_in_one_does_not_affect_other(self):
        """Error in ws1 does not affect ws2."""
        ws1 = _advance_to_state('ws-1', 'bootstrapping', 0)
        ws2 = _advance_to_state('ws-2', 'bootstrapping', 10)

        ws1 = transition_to_error(
            ws1, now=_t(50), error_code='oom', error_detail='out of memory',
        )
        assert ws1.state == 'error'
        assert ws2.state == 'bootstrapping'

        ws2 = advance_state(ws2, now=_t(51))
        assert ws2.state == 'health_check'

    def test_retry_one_while_other_is_ready(self):
        """ws1 retries while ws2 is already ready."""
        ws1 = _advance_to_state('ws-1', 'uploading_artifact', 0)
        ws2 = _advance_to_ready('ws-2', 0)

        ws1 = transition_to_error(
            ws1, now=_t(20),
            error_code='upload_fail', error_detail='timeout',
        )
        ws1 = retry_from_error(ws1, now=_t(30))
        assert ws1.state == 'queued'
        assert ws1.attempt == 2
        assert ws2.state == 'ready'

    def test_sandbox_names_are_distinct(self):
        """Different workspaces produce different sandbox names."""
        names = set()
        for ws_id in ['ws-1', 'ws-2', 'ws-3']:
            name = build_sandbox_name(
                app_id='app', workspace_id=ws_id, env='prod',
            )
            names.add(name)
        assert len(names) == 3


# =====================================================================
# 9. Observability compatibility
# =====================================================================


class TestObservabilityCompatibility:
    """Error codes and state labels are compatible with metric dimensions."""

    def test_step_timeout_code_is_constant(self):
        """STEP_TIMEOUT code matches expected metric label."""
        assert STEP_TIMEOUT_CODE == 'STEP_TIMEOUT'

    def test_release_unavailable_code_is_constant(self):
        """release_unavailable code matches expected metric label."""
        assert RELEASE_UNAVAILABLE_CODE == 'release_unavailable'

    def test_error_codes_are_non_empty_strings(self):
        """All error codes used in transitions are non-empty."""
        job = _advance_to_state('ws-codes', 'health_check', 0)

        codes = ['STEP_TIMEOUT', 'ARTIFACT_CHECKSUM_MISMATCH', 'upstream_error']
        for code in codes:
            errored = transition_to_error(
                job, now=_t(50), error_code=code, error_detail='test',
            )
            assert errored.last_error_code == code
            assert len(code) > 0

    def test_state_labels_are_lowercase_underscore(self):
        """State names are lowercase with underscores (metric-friendly)."""
        for state in PROVISIONING_SEQUENCE:
            assert state == state.lower()
            assert ' ' not in state
        assert 'error' == 'error'.lower()

    def test_terminal_states_set_finished_at(self):
        """Both terminal states (ready, error) set finished_at for duration tracking."""
        ready = _advance_to_ready('ws-obs-rdy', 0)
        assert ready.finished_at is not None

        job = _advance_to_state('ws-obs-err', 'release_resolve', 0)
        errored = transition_to_error(
            job, now=_t(5), error_code='x', error_detail='x',
        )
        assert errored.finished_at is not None


# =====================================================================
# 10. Error code semantics
# =====================================================================


class TestErrorCodeSemantics:
    """Verify different failure types produce distinguishable error codes."""

    def test_timeout_error_includes_step_name(self):
        """STEP_TIMEOUT detail includes which step timed out."""
        for step in ('release_resolve', 'creating_sandbox', 'health_check'):
            job = _advance_to_state('ws-detail', step, 0)
            timed_out = apply_step_timeout(job, now=_t(9999))
            assert timed_out.last_error_code == STEP_TIMEOUT_CODE
            assert step in timed_out.last_error_detail

    def test_timeout_detail_includes_elapsed_time(self):
        """Timeout detail includes actual elapsed seconds."""
        job = _advance_to_state('ws-elapsed', 'bootstrapping', 0)
        seq_idx = PROVISIONING_SEQUENCE.index('bootstrapping')
        timeout = DEFAULT_STEP_TIMEOUT_SECONDS['bootstrapping']
        elapsed = timeout + 42

        timed_out = apply_step_timeout(job, now=_t(seq_idx + elapsed))
        detail = timed_out.last_error_detail or ''
        assert str(elapsed) in detail or str(elapsed - 1) in detail

    def test_custom_error_code_preserved(self):
        """Application-defined error codes are preserved exactly."""
        job = _advance_to_state('ws-custom', 'uploading_artifact', 0)
        errored = transition_to_error(
            job, now=_t(50),
            error_code='ARTIFACT_CHECKSUM_MISMATCH',
            error_detail='expected abc got def',
        )
        assert errored.last_error_code == 'ARTIFACT_CHECKSUM_MISMATCH'
        assert 'abc' in errored.last_error_detail
        assert 'def' in errored.last_error_detail


# =====================================================================
# 11. Provisioning target and sandbox name integration
# =====================================================================


class TestProvisioningTargetIntegration:
    """Verify provisioning target flows into state machine correctly."""

    def test_target_workspace_id_matches_job(
        self,
        artifact_store: FileSystemArtifactStore,
        bundle_file: Path,
    ):
        """Target workspace_id is used to create the job."""
        _publish_test_release(artifact_store, bundle_file, 'app', 'v1')

        target = resolve_provisioning_target(
            app_id='app', workspace_id='ws-target', env='prod',
            requested_release_id='v1', default_release_id=None,
            artifact_lookup=artifact_store,
        )

        job = create_queued_job(
            workspace_id=target.workspace_id, now=_t(0),
        )
        assert job.workspace_id == 'ws-target'

    def test_default_release_fallback_integration(
        self,
        artifact_store: FileSystemArtifactStore,
        bundle_file: Path,
    ):
        """Default release_id works when no explicit request."""
        _publish_test_release(artifact_store, bundle_file, 'app', 'v-default')

        target = resolve_provisioning_target(
            app_id='app', workspace_id='ws-1', env='staging',
            requested_release_id=None, default_release_id='v-default',
            artifact_lookup=artifact_store,
        )
        assert target.release_id == 'v-default'
        assert target.sandbox_name == 'sbx-app-ws-1-staging'

    def test_no_release_no_default_raises(
        self, artifact_store: FileSystemArtifactStore,
    ):
        """No release and no default raises ReleaseUnavailableError."""
        with pytest.raises(ReleaseUnavailableError) as exc_info:
            resolve_provisioning_target(
                app_id='app', workspace_id='ws-1', env='prod',
                requested_release_id=None, default_release_id=None,
                artifact_lookup=artifact_store,
            )
        assert exc_info.value.reason == 'no_release_available'
