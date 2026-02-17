"""Concurrent create/retry load tests for provisioning service.

Bead: bd-223o.10.3.1 (D3a)

Stress concurrent create/retry requests to validate dedupe and lock
invariants:

  1. Idempotency dedup under concurrency: N callers with same key → 1 job.
  2. Single-active-job under contention: N callers with different keys →
     1 created, N-1 get ActiveJobConflict.
  3. Rapid retry button: N retry calls with same key → 1 job.
  4. Cross-workspace isolation: concurrent creates for different workspaces
     never interfere.
  5. Mixed create/retry under contention: interleaved calls still uphold
     invariants.
"""

from __future__ import annotations

import asyncio

import pytest

from control_plane.app.provisioning.job_service import (
    ActiveJobConflict,
    CreateJobResult,
    InMemoryProvisioningJobRepository,
    ProvisioningService,
)


@pytest.fixture
def repo():
    return InMemoryProvisioningJobRepository()


@pytest.fixture
def service(repo):
    return ProvisioningService(repo)


# =====================================================================
# 1. Idempotency dedup under concurrency
# =====================================================================


class TestConcurrentIdempotencyDedup:
    """Multiple concurrent callers with the same idempotency_key."""

    @pytest.mark.asyncio
    async def test_10_concurrent_creates_same_key_one_created(self, service):
        """Fire 10 creates with the same key → exactly 1 marked created."""
        tasks = [
            service.create_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='shared-key-1',
                created_by=f'user_{i}',
            )
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        created_count = sum(1 for r in results if r.created)
        deduped_count = sum(1 for r in results if not r.created)
        assert created_count == 1
        assert deduped_count == 9

    @pytest.mark.asyncio
    async def test_all_deduped_share_same_job_id(self, service):
        """All 10 results reference the same job."""
        tasks = [
            service.create_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='shared-key-2',
                created_by=f'user_{i}',
            )
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        job_ids = {r.job.id for r in results}
        assert len(job_ids) == 1

    @pytest.mark.asyncio
    async def test_50_concurrent_creates_same_key(self, service):
        """Scale to 50 concurrent callers — still exactly 1 created."""
        tasks = [
            service.create_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='bulk-key',
                created_by=f'user_{i}',
            )
            for i in range(50)
        ]
        results = await asyncio.gather(*tasks)

        created_count = sum(1 for r in results if r.created)
        assert created_count == 1
        assert all(r.job.workspace_id == 'ws_abc' for r in results)


# =====================================================================
# 2. Single-active-job under contention
# =====================================================================


class TestConcurrentSingleActiveJob:
    """Multiple concurrent callers with different idempotency keys."""

    @pytest.mark.asyncio
    async def test_concurrent_different_keys_one_wins(self, service):
        """10 creates with different keys → 1 created, 9 conflicts."""
        results: list[CreateJobResult | ActiveJobConflict] = []

        async def try_create(i: int):
            try:
                return await service.create_provisioning_job(
                    workspace_id='ws_abc',
                    idempotency_key=f'key-{i}',
                    created_by=f'user_{i}',
                )
            except ActiveJobConflict as exc:
                return exc

        tasks = [try_create(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        created = [r for r in results if isinstance(r, CreateJobResult)]
        conflicts = [r for r in results if isinstance(r, ActiveJobConflict)]

        assert len(created) == 1
        assert len(conflicts) == 9
        assert created[0].created is True

    @pytest.mark.asyncio
    async def test_conflicts_reference_correct_workspace(self, service):
        """ActiveJobConflict errors identify the workspace."""
        async def try_create(i: int):
            try:
                return await service.create_provisioning_job(
                    workspace_id='ws_contention',
                    idempotency_key=f'ck-{i}',
                    created_by=f'user_{i}',
                )
            except ActiveJobConflict as exc:
                return exc

        tasks = [try_create(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        conflicts = [r for r in results if isinstance(r, ActiveJobConflict)]
        for c in conflicts:
            assert c.workspace_id == 'ws_contention'
            assert c.active_job_id >= 1


# =====================================================================
# 3. Rapid retry button simulation
# =====================================================================


class TestRapidRetryButton:
    """Simulate user rapidly clicking retry with same idempotency key."""

    @pytest.mark.asyncio
    async def test_rapid_retry_3x_one_job(self, service):
        """3 rapid retries with the same key → exactly 1 created."""
        tasks = [
            service.retry_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='retry-rapid-1',
                created_by='user_1',
            )
            for _ in range(3)
        ]
        results = await asyncio.gather(*tasks)

        created_count = sum(1 for r in results if r.created)
        assert created_count == 1

    @pytest.mark.asyncio
    async def test_rapid_retry_10x_one_job(self, service):
        """10 rapid retries → exactly 1 created, all same job."""
        tasks = [
            service.retry_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='retry-rapid-10',
                created_by='user_1',
            )
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)

        created_count = sum(1 for r in results if r.created)
        job_ids = {r.job.id for r in results}
        assert created_count == 1
        assert len(job_ids) == 1

    @pytest.mark.asyncio
    async def test_retry_after_error_then_rapid_retry(self, service, repo):
        """Create job → error → rapid retries with new key → 1 new job."""
        original = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='original-key',
            created_by='user_1',
        )
        # Simulate error state (terminal, no longer active).
        original.job.state = 'error'

        tasks = [
            service.retry_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='retry-after-error',
                created_by='user_1',
            )
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)

        created_count = sum(1 for r in results if r.created)
        assert created_count == 1
        # New job has different ID from original.
        assert all(r.job.id != original.job.id for r in results)


# =====================================================================
# 4. Cross-workspace isolation under concurrency
# =====================================================================


class TestCrossWorkspaceIsolation:
    """Concurrent creates for different workspaces never interfere."""

    @pytest.mark.asyncio
    async def test_10_workspaces_concurrent(self, service):
        """Create jobs for 10 different workspaces concurrently → all succeed."""
        tasks = [
            service.create_provisioning_job(
                workspace_id=f'ws_{i}',
                idempotency_key=f'key_{i}',
                created_by='user_1',
            )
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r.created is True for r in results)
        workspace_ids = {r.job.workspace_id for r in results}
        assert len(workspace_ids) == 10

    @pytest.mark.asyncio
    async def test_workspace_isolation_no_cross_dedup(self, service):
        """Same idempotency key in different workspaces → separate jobs."""
        tasks = [
            service.create_provisioning_job(
                workspace_id=f'ws_{i}',
                idempotency_key='shared-key',
                created_by='user_1',
            )
            for i in range(5)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r.created is True for r in results)
        job_ids = {r.job.id for r in results}
        assert len(job_ids) == 5  # All distinct.


# =====================================================================
# 5. Mixed create/retry contention
# =====================================================================


class TestMixedCreateRetryContention:
    """Interleaved create and retry calls under contention."""

    @pytest.mark.asyncio
    async def test_mixed_create_retry_same_key(self, service):
        """Interleave create + retry with same key → exactly 1 job."""
        tasks = []
        for i in range(5):
            if i % 2 == 0:
                tasks.append(service.create_provisioning_job(
                    workspace_id='ws_abc',
                    idempotency_key='mixed-key',
                    created_by=f'user_{i}',
                ))
            else:
                tasks.append(service.retry_provisioning_job(
                    workspace_id='ws_abc',
                    idempotency_key='mixed-key',
                    created_by=f'user_{i}',
                ))

        results = await asyncio.gather(*tasks)

        created_count = sum(1 for r in results if r.created)
        job_ids = {r.job.id for r in results}
        assert created_count == 1
        assert len(job_ids) == 1

    @pytest.mark.asyncio
    async def test_mixed_contention_different_keys_one_active(self, service):
        """Interleave create+retry with different keys → 1 active, rest conflict."""
        async def try_op(i: int):
            try:
                if i % 2 == 0:
                    return await service.create_provisioning_job(
                        workspace_id='ws_abc',
                        idempotency_key=f'mixed-{i}',
                        created_by=f'user_{i}',
                    )
                else:
                    return await service.retry_provisioning_job(
                        workspace_id='ws_abc',
                        idempotency_key=f'mixed-{i}',
                        created_by=f'user_{i}',
                    )
            except ActiveJobConflict as exc:
                return exc

        tasks = [try_op(i) for i in range(8)]
        results = await asyncio.gather(*tasks)

        created = [r for r in results if isinstance(r, CreateJobResult)]
        conflicts = [r for r in results if isinstance(r, ActiveJobConflict)]

        assert len(created) == 1
        assert len(conflicts) == 7


# =====================================================================
# 6. Sequential rounds of contention
# =====================================================================


class TestSequentialRounds:
    """Multiple rounds of contention after job lifecycle completes."""

    @pytest.mark.asyncio
    async def test_three_rounds_of_concurrent_creates(self, service, repo):
        """Create → error → create → error → create: each round 1 job."""
        for round_num in range(3):
            tasks = [
                service.create_provisioning_job(
                    workspace_id='ws_abc',
                    idempotency_key=f'round-{round_num}-key',
                    created_by='user_1',
                )
                for _ in range(5)
            ]
            results = await asyncio.gather(*tasks)

            created_count = sum(1 for r in results if r.created)
            assert created_count == 1, (
                f'round {round_num}: expected 1 created, got {created_count}'
            )

            # Transition job to error (terminal) so next round can create.
            created_job = next(r for r in results if r.created).job
            created_job.state = 'error'

    @pytest.mark.asyncio
    async def test_job_count_after_rounds(self, service, repo):
        """After 3 rounds of concurrent creates, total 3 jobs exist."""
        for round_num in range(3):
            result = await service.create_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key=f'counting-{round_num}',
                created_by='user_1',
            )
            result.job.state = 'error'

        # 3 jobs exist (all terminal).
        assert len(repo._jobs) == 3
