"""Tests for provisioning error code mapping and actionable details.

Bead: bd-223o.10.2.1 (D2a)

Validates:
  - ARTIFACT_CHECKSUM_MISMATCH error code constant and transition helper
  - STEP_TIMEOUT error code is emitted with actionable detail
  - format_checksum_mismatch_detail produces actionable output
  - format_step_timeout_detail produces actionable output
  - transition_to_checksum_mismatch creates correct error state
  - Error codes match frontend expectations (STEP_TIMEOUT, ARTIFACT_CHECKSUM_MISMATCH)
  - Retry from checksum mismatch error clears error state
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from control_plane.app.provisioning.state_machine import (
    ARTIFACT_CHECKSUM_MISMATCH_CODE,
    DEFAULT_STEP_TIMEOUT_SECONDS,
    STEP_TIMEOUT_CODE,
    InvalidStateTransition,
    advance_state,
    apply_step_timeout,
    create_queued_job,
    format_checksum_mismatch_detail,
    format_step_timeout_detail,
    retry_from_error,
    transition_to_checksum_mismatch,
    transition_to_error,
)


def _t(seconds: int) -> datetime:
    return datetime(2026, 2, 13, 12, 0, 0, tzinfo=UTC) + timedelta(
        seconds=seconds
    )


# =====================================================================
# 1. Error code constants
# =====================================================================


class TestErrorCodeConstants:

    def test_step_timeout_code_value(self):
        assert STEP_TIMEOUT_CODE == 'STEP_TIMEOUT'

    def test_artifact_checksum_mismatch_code_value(self):
        assert ARTIFACT_CHECKSUM_MISMATCH_CODE == 'ARTIFACT_CHECKSUM_MISMATCH'

    def test_codes_are_distinct(self):
        assert STEP_TIMEOUT_CODE != ARTIFACT_CHECKSUM_MISMATCH_CODE

    def test_codes_match_frontend_expectations(self):
        """Frontend ProvisioningError.jsx expects these exact string values."""
        frontend_expected = {'STEP_TIMEOUT', 'ARTIFACT_CHECKSUM_MISMATCH'}
        backend_codes = {STEP_TIMEOUT_CODE, ARTIFACT_CHECKSUM_MISMATCH_CODE}
        assert backend_codes == frontend_expected


# =====================================================================
# 2. format_checksum_mismatch_detail
# =====================================================================


class TestFormatChecksumMismatchDetail:

    def test_includes_expected_hash_prefix(self):
        detail = format_checksum_mismatch_detail(
            expected_sha256='abcdef1234567890' * 4,
            actual_sha256='0000000000000000' * 4,
        )
        assert 'abcdef1234567890' in detail

    def test_includes_actual_hash_prefix(self):
        detail = format_checksum_mismatch_detail(
            expected_sha256='abcdef1234567890' * 4,
            actual_sha256='0000111122223333' * 4,
        )
        assert '0000111122223333' in detail

    def test_includes_remediation_guidance(self):
        detail = format_checksum_mismatch_detail(
            expected_sha256='a' * 64,
            actual_sha256='b' * 64,
        )
        assert 'republished' in detail

    def test_truncates_hashes_for_readability(self):
        """Full 64-char hashes should not appear; truncated prefixes only."""
        expected = 'a' * 64
        actual = 'b' * 64
        detail = format_checksum_mismatch_detail(
            expected_sha256=expected,
            actual_sha256=actual,
        )
        assert expected not in detail
        assert actual not in detail


# =====================================================================
# 3. format_step_timeout_detail
# =====================================================================


class TestFormatStepTimeoutDetail:

    def test_includes_step_name(self):
        detail = format_step_timeout_detail(
            step='uploading_artifact',
            elapsed_seconds=90,
            timeout_seconds=60,
        )
        assert 'uploading_artifact' in detail

    def test_includes_elapsed_seconds(self):
        detail = format_step_timeout_detail(
            step='health_check',
            elapsed_seconds=45,
            timeout_seconds=30,
        )
        assert '45' in detail

    def test_includes_timeout_seconds(self):
        detail = format_step_timeout_detail(
            step='health_check',
            elapsed_seconds=45,
            timeout_seconds=30,
        )
        assert '30' in detail

    def test_shows_exceeded_relationship(self):
        detail = format_step_timeout_detail(
            step='bootstrapping',
            elapsed_seconds=150,
            timeout_seconds=120,
        )
        assert '>' in detail


# =====================================================================
# 4. transition_to_checksum_mismatch
# =====================================================================


class TestTransitionToChecksumMismatch:

    def test_transitions_active_step_to_error(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))  # release_resolve
        job = advance_state(job, now=_t(2))  # creating_sandbox
        job = advance_state(job, now=_t(3))  # uploading_artifact

        error_job = transition_to_checksum_mismatch(
            job,
            now=_t(4),
            expected_sha256='a' * 64,
            actual_sha256='b' * 64,
        )

        assert error_job.state == 'error'
        assert error_job.last_error_code == ARTIFACT_CHECKSUM_MISMATCH_CODE
        assert error_job.finished_at == _t(4)

    def test_error_detail_is_actionable(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))

        error_job = transition_to_checksum_mismatch(
            job,
            now=_t(2),
            expected_sha256='abc123' + '0' * 58,
            actual_sha256='def456' + '0' * 58,
        )

        assert error_job.last_error_detail is not None
        assert 'mismatch' in error_job.last_error_detail.lower()
        assert 'republished' in error_job.last_error_detail

    def test_rejects_queued_state(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))

        with pytest.raises(InvalidStateTransition):
            transition_to_checksum_mismatch(
                job,
                now=_t(1),
                expected_sha256='a' * 64,
                actual_sha256='b' * 64,
            )

    def test_rejects_terminal_ready_state(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        for i in range(1, 7):
            job = advance_state(job, now=_t(i))
        assert job.state == 'ready'

        with pytest.raises(InvalidStateTransition):
            transition_to_checksum_mismatch(
                job,
                now=_t(8),
                expected_sha256='a' * 64,
                actual_sha256='b' * 64,
            )

    def test_rejects_naive_datetime(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))

        with pytest.raises(ValueError, match='timezone-aware'):
            transition_to_checksum_mismatch(
                job,
                now=datetime(2026, 2, 13, 12, 0, 0),
                expected_sha256='a' * 64,
                actual_sha256='b' * 64,
            )

    def test_preserves_attempt_count(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))

        error_job = transition_to_checksum_mismatch(
            job,
            now=_t(2),
            expected_sha256='a' * 64,
            actual_sha256='b' * 64,
        )

        assert error_job.attempt == 1


# =====================================================================
# 5. Retry after checksum mismatch
# =====================================================================


class TestRetryAfterChecksumMismatch:

    def test_retry_clears_checksum_error(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))

        error_job = transition_to_checksum_mismatch(
            job,
            now=_t(2),
            expected_sha256='a' * 64,
            actual_sha256='b' * 64,
        )
        assert error_job.state == 'error'
        assert error_job.last_error_code == ARTIFACT_CHECKSUM_MISMATCH_CODE

        retried = retry_from_error(error_job, now=_t(3))
        assert retried.state == 'queued'
        assert retried.attempt == 2
        assert retried.last_error_code is None
        assert retried.last_error_detail is None

    def test_retry_increments_attempt(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))
        job = transition_to_checksum_mismatch(
            job,
            now=_t(2),
            expected_sha256='a' * 64,
            actual_sha256='b' * 64,
        )
        retried = retry_from_error(job, now=_t(3))
        assert retried.attempt == 2


# =====================================================================
# 6. Step timeout emits correct code (existing behavior verification)
# =====================================================================


class TestStepTimeoutCode:

    def test_timeout_emits_step_timeout_code(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))  # release_resolve
        timeout = DEFAULT_STEP_TIMEOUT_SECONDS['release_resolve']

        timed_out = apply_step_timeout(job, now=_t(1 + timeout + 1))

        assert timed_out.state == 'error'
        assert timed_out.last_error_code == STEP_TIMEOUT_CODE
        assert timed_out.last_error_code == 'STEP_TIMEOUT'

    def test_timeout_detail_includes_step_name(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))
        timeout = DEFAULT_STEP_TIMEOUT_SECONDS['release_resolve']

        timed_out = apply_step_timeout(job, now=_t(1 + timeout + 1))

        assert 'release_resolve' in (timed_out.last_error_detail or '')

    def test_timeout_detail_includes_elapsed(self):
        job = create_queued_job(workspace_id='ws_123', now=_t(0))
        job = advance_state(job, now=_t(1))
        timeout = DEFAULT_STEP_TIMEOUT_SECONDS['release_resolve']
        elapsed = timeout + 5

        timed_out = apply_step_timeout(job, now=_t(1 + elapsed))

        detail = timed_out.last_error_detail or ''
        assert str(elapsed) in detail


# =====================================================================
# 7. Package-level imports work
# =====================================================================


class TestPackageExports:

    def test_import_from_package(self):
        from control_plane.app.provisioning import (
            ARTIFACT_CHECKSUM_MISMATCH_CODE,
            STEP_TIMEOUT_CODE,
            format_checksum_mismatch_detail,
            format_step_timeout_detail,
            transition_to_checksum_mismatch,
        )
        assert ARTIFACT_CHECKSUM_MISMATCH_CODE == 'ARTIFACT_CHECKSUM_MISMATCH'
        assert STEP_TIMEOUT_CODE == 'STEP_TIMEOUT'
        assert callable(format_checksum_mismatch_detail)
        assert callable(format_step_timeout_detail)
        assert callable(transition_to_checksum_mismatch)
