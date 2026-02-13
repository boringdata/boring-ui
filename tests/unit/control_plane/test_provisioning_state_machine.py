"""Provisioning state-machine tests.

Bead: bd-223o.10.2 (D2)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from control_plane.app.provisioning.state_machine import (
    DEFAULT_STEP_TIMEOUT_SECONDS,
    STEP_TIMEOUT_CODE,
    InvalidStateTransition,
    advance_state,
    apply_step_timeout,
    create_queued_job,
    retry_from_error,
    transition_to_error,
)


def _t(seconds: int) -> datetime:
    return datetime(2026, 2, 13, 12, 0, 0, tzinfo=UTC) + timedelta(
        seconds=seconds
    )


class TestCreateQueuedJob:
    def test_defaults(self):
        job = create_queued_job(workspace_id='ws_123')
        assert job.state == 'queued'
        assert job.attempt == 1
        assert job.last_error_code is None
        assert job.finished_at is None

    def test_rejects_invalid_attempt(self):
        with pytest.raises(ValueError, match='attempt must be >= 1'):
            create_queued_job(workspace_id='ws_123', attempt=0)

    def test_rejects_naive_now(self):
        with pytest.raises(ValueError, match='timezone-aware'):
            create_queued_job(
                workspace_id='ws_123',
                now=datetime(2026, 2, 13, 12, 0, 0),
            )


class TestDeterministicTransitions:
    def test_advance_to_ready(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))
        assert job.state == 'release_resolve'
        job = advance_state(job, now=_t(2))
        assert job.state == 'creating_sandbox'
        job = advance_state(job, now=_t(3))
        assert job.state == 'uploading_artifact'
        job = advance_state(job, now=_t(4))
        assert job.state == 'bootstrapping'
        job = advance_state(job, now=_t(5))
        assert job.state == 'health_check'
        job = advance_state(job, now=_t(6))
        assert job.state == 'ready'
        assert job.finished_at == _t(6)

    def test_advance_from_ready_is_invalid(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        for i in range(1, 7):
            job = advance_state(job, now=_t(i))
        with pytest.raises(InvalidStateTransition):
            advance_state(job, now=_t(8))

    def test_advance_from_error_is_invalid(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))
        job = transition_to_error(
            job,
            now=_t(2),
            error_code='artifact_error',
            error_detail='bad checksum',
        )
        with pytest.raises(InvalidStateTransition):
            advance_state(job, now=_t(3))


class TestErrorAndRetry:
    def test_active_step_can_transition_to_error(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))
        error = transition_to_error(
            job,
            now=_t(2),
            error_code='failure',
            error_detail='something failed',
        )
        assert error.state == 'error'
        assert error.finished_at == _t(2)
        assert error.last_error_code == 'failure'

    def test_queued_to_error_is_invalid(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        with pytest.raises(InvalidStateTransition):
            transition_to_error(
                job,
                now=_t(1),
                error_code='x',
                error_detail='x',
            )

    def test_retry_from_error_returns_queued_and_increments_attempt(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))
        job = transition_to_error(
            job,
            now=_t(2),
            error_code='upstream',
            error_detail='upstream failed',
        )
        retried = retry_from_error(job, now=_t(3))
        assert retried.state == 'queued'
        assert retried.attempt == 2
        assert retried.last_error_code is None
        assert retried.last_error_detail is None


class TestStepTimeouts:
    def test_timeout_moves_step_to_error(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))  # release_resolve
        timeout_seconds = DEFAULT_STEP_TIMEOUT_SECONDS['release_resolve']
        timed_out = apply_step_timeout(
            job,
            now=_t(1 + timeout_seconds + 1),
        )
        assert timed_out.state == 'error'
        assert timed_out.last_error_code == STEP_TIMEOUT_CODE
        assert 'release_resolve' in (timed_out.last_error_detail or '')

    def test_timeout_noop_for_non_timed_out_step(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))
        timeout_seconds = DEFAULT_STEP_TIMEOUT_SECONDS['release_resolve']
        same = apply_step_timeout(job, now=_t(1 + timeout_seconds))
        assert same == job

    def test_timeout_noop_for_terminal_or_queued(self):
        queued = create_queued_job(workspace_id='ws_123', now=_t(0))
        assert apply_step_timeout(queued, now=_t(100)) == queued

        ready = create_queued_job(workspace_id='ws_123', now=_t(0))
        for i in range(1, 7):
            ready = advance_state(ready, now=_t(i))
        assert ready.state == 'ready'
        assert apply_step_timeout(ready, now=_t(200)) == ready


class TestDateValidation:
    def test_rejects_naive_datetime(self):
        naive = datetime(2026, 2, 13, 12, 0, 0)
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        with pytest.raises(ValueError, match='timezone-aware'):
            advance_state(job, now=naive)
