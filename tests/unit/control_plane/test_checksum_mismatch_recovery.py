"""Checksum-mismatch handling and retry recovery tests.

Bead: bd-223o.10.4.1 (D4a)

Validates:
  1. Corrupted artifact transitions to error with ARTIFACT_CHECKSUM_MISMATCH.
  2. Error details include expected/actual SHA-256 information.
  3. After artifact repair, retry succeeds through full flow to ready.
  4. Retry with same idempotency key deduplicates correctly.
  5. Runtime metadata reflects error → retry → ready lifecycle.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from control_plane.app.provisioning.job_executor import (
    InMemoryArtifactVerifier,
    InMemoryRuntimeMetadataStore,
    InMemorySandboxProvider,
    ProvisioningJobExecutor,
)
from control_plane.app.provisioning.job_service import (
    InMemoryProvisioningJobRepository,
    ProvisioningService,
)
from control_plane.app.provisioning.release_contract import ProvisioningTarget
from control_plane.app.provisioning.state_machine import (
    ARTIFACT_CHECKSUM_MISMATCH_CODE,
    STEP_TIMEOUT_CODE,
    ProvisioningJobState,
    advance_state,
    create_queued_job,
    format_checksum_mismatch_detail,
    retry_from_error,
    transition_to_checksum_mismatch,
    transition_to_error,
)


def _make_target(**overrides) -> ProvisioningTarget:
    defaults = {
        'app_id': 'boring-ui',
        'workspace_id': 'ws_test',
        'release_id': 'rel-001',
        'sandbox_name': 'sbx-boring-ui-ws-test-dev',
        'bundle_sha256': 'abc123def456',
    }
    defaults.update(overrides)
    return ProvisioningTarget(**defaults)


# ── Checksum mismatch error path ─────────────────────────────────────


class TestChecksumMismatchError:
    @pytest.mark.asyncio
    async def test_corrupted_artifact_yields_checksum_error(self):
        """Corrupted bundle → executor returns ARTIFACT_CHECKSUM_MISMATCH."""
        verifier = InMemoryArtifactVerifier(valid=False)
        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=verifier,
            runtime_store=InMemoryRuntimeMetadataStore(),
        )

        result = await executor.execute(target=_make_target())

        assert result.success is False
        assert result.error_code == ARTIFACT_CHECKSUM_MISMATCH_CODE
        assert result.job.state == 'error'
        assert result.job.last_error_code == ARTIFACT_CHECKSUM_MISMATCH_CODE

    @pytest.mark.asyncio
    async def test_error_detail_is_actionable(self):
        """Error detail includes SHA-256 mismatch context."""
        verifier = InMemoryArtifactVerifier(valid=False)
        runtime = InMemoryRuntimeMetadataStore()
        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=verifier,
            runtime_store=runtime,
        )

        result = await executor.execute(target=_make_target())

        # Error detail should mention "mismatch" and be non-empty.
        assert result.error_detail is not None
        assert 'mismatch' in result.error_detail.lower()

    @pytest.mark.asyncio
    async def test_runtime_persists_checksum_error(self):
        """Runtime metadata reflects ARTIFACT_CHECKSUM_MISMATCH error."""
        verifier = InMemoryArtifactVerifier(valid=False)
        runtime = InMemoryRuntimeMetadataStore()
        executor = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=verifier,
            runtime_store=runtime,
        )

        await executor.execute(target=_make_target())

        rt = runtime.runtimes['ws_test']
        assert rt['state'] == 'error'
        assert rt['last_error_code'] == ARTIFACT_CHECKSUM_MISMATCH_CODE

    @pytest.mark.asyncio
    async def test_no_sandbox_work_on_checksum_failure(self):
        """No sandbox calls when artifact verification fails."""
        sandbox = InMemorySandboxProvider()
        verifier = InMemoryArtifactVerifier(valid=False)
        executor = ProvisioningJobExecutor(
            sandbox_provider=sandbox,
            artifact_verifier=verifier,
            runtime_store=InMemoryRuntimeMetadataStore(),
        )

        await executor.execute(target=_make_target())

        assert len(sandbox.calls) == 0


# ── Retry recovery after checksum fix ────────────────────────────────


class TestRetryRecoveryAfterChecksumFix:
    @pytest.mark.asyncio
    async def test_retry_succeeds_after_artifact_repaired(self):
        """First attempt fails (bad checksum), retry with fixed artifact succeeds."""
        runtime = InMemoryRuntimeMetadataStore()

        # Attempt 1: corrupted artifact.
        bad_verifier = InMemoryArtifactVerifier(valid=False)
        executor_1 = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=bad_verifier,
            runtime_store=runtime,
        )
        result_1 = await executor_1.execute(target=_make_target())
        assert result_1.success is False
        assert result_1.error_code == ARTIFACT_CHECKSUM_MISMATCH_CODE

        # Runtime should show error state.
        assert runtime.runtimes['ws_test']['state'] == 'error'

        # Attempt 2: repaired artifact.
        good_verifier = InMemoryArtifactVerifier(
            valid=True,
            bundle_file=Path('/tmp/repaired-bundle.tar.gz'),
        )
        executor_2 = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=good_verifier,
            runtime_store=runtime,
        )
        result_2 = await executor_2.execute(target=_make_target())
        assert result_2.success is True
        assert result_2.job.state == 'ready'

        # Runtime should now show ready.
        assert runtime.runtimes['ws_test']['state'] == 'ready'
        assert runtime.runtimes['ws_test']['last_error_code'] is None

    @pytest.mark.asyncio
    async def test_retry_preserves_target_metadata(self):
        """Retry persists correct release_id and bundle_sha256."""
        runtime = InMemoryRuntimeMetadataStore()
        target = _make_target(
            release_id='v2.0.1',
            bundle_sha256='sha256_correct',
        )

        # Fail first.
        executor_bad = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(valid=False),
            runtime_store=runtime,
        )
        await executor_bad.execute(target=target)

        # Succeed on retry.
        executor_good = ProvisioningJobExecutor(
            sandbox_provider=InMemorySandboxProvider(),
            artifact_verifier=InMemoryArtifactVerifier(
                valid=True,
                bundle_file=Path('/tmp/bundle.tar.gz'),
            ),
            runtime_store=runtime,
        )
        await executor_good.execute(target=target)

        rt = runtime.runtimes[target.workspace_id]
        assert rt['release_id'] == 'v2.0.1'
        assert rt['bundle_sha256'] == 'sha256_correct'
        assert rt['state'] == 'ready'


# ── Idempotent retry through service ─────────────────────────────────


class TestIdempotentRetryWithService:
    @pytest.mark.asyncio
    async def test_service_retry_after_error(self):
        """ProvisioningService allows retry after error'd job."""
        repo = InMemoryProvisioningJobRepository()
        service = ProvisioningService(repo)

        # Create initial job.
        result_1 = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='attempt-1',
            created_by='user_1',
        )
        assert result_1.created is True

        # Simulate job reaching error state.
        result_1.job.state = 'error'

        # Retry with new idempotency key should succeed.
        result_2 = await service.retry_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='attempt-2',
            created_by='user_1',
        )
        assert result_2.created is True
        assert result_2.job.id != result_1.job.id

    @pytest.mark.asyncio
    async def test_service_retry_with_same_key_deduplicates(self):
        """Same idempotency key on retry returns existing job."""
        repo = InMemoryProvisioningJobRepository()
        service = ProvisioningService(repo)

        result_1 = await service.retry_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='retry-key',
            created_by='user_1',
        )
        result_2 = await service.retry_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='retry-key',
            created_by='user_1',
        )

        assert result_1.created is True
        assert result_2.created is False
        assert result_2.job.id == result_1.job.id


# ── State machine checksum transitions ───────────────────────────────


class TestStateMachineChecksumTransitions:
    def test_checksum_mismatch_from_release_resolve(self):
        """transition_to_checksum_mismatch works from release_resolve."""
        from datetime import UTC, datetime, timedelta

        now = datetime(2026, 2, 13, 12, 0, 0, tzinfo=UTC)
        job = create_queued_job(workspace_id='ws_1', now=now)
        job = advance_state(job, now=now + timedelta(seconds=1))
        assert job.state == 'release_resolve'

        error_job = transition_to_checksum_mismatch(
            job,
            now=now + timedelta(seconds=2),
            expected_sha256='aaa111',
            actual_sha256='bbb222',
        )
        assert error_job.state == 'error'
        assert error_job.last_error_code == ARTIFACT_CHECKSUM_MISMATCH_CODE

    def test_checksum_detail_includes_hashes(self):
        """format_checksum_mismatch_detail includes truncated hashes."""
        detail = format_checksum_mismatch_detail(
            expected_sha256='abcdef1234567890abcdef',
            actual_sha256='1234567890abcdef1234567890',
        )
        assert 'abcdef1234567890' in detail
        assert '1234567890abcdef' in detail
        assert 'mismatch' in detail.lower()

    def test_retry_from_checksum_error_resets_to_queued(self):
        """After checksum error, retry_from_error returns to queued."""
        from datetime import UTC, datetime, timedelta

        now = datetime(2026, 2, 13, 12, 0, 0, tzinfo=UTC)
        job = create_queued_job(workspace_id='ws_1', now=now)
        job = advance_state(job, now=now + timedelta(seconds=1))
        job = transition_to_checksum_mismatch(
            job,
            now=now + timedelta(seconds=2),
            expected_sha256='aaa',
            actual_sha256='bbb',
        )
        assert job.state == 'error'

        retried = retry_from_error(job, now=now + timedelta(seconds=3))
        assert retried.state == 'queued'
        assert retried.attempt == 2
        assert retried.last_error_code is None
