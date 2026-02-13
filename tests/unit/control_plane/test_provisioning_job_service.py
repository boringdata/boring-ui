"""Provisioning job service tests: idempotency + single-active-job.

Bead: bd-223o.10.3 (D3)
"""

from __future__ import annotations

import pytest

from control_plane.app.provisioning.job_service import (
    ActiveJobConflict,
    IdempotencyKeyRequired,
    InMemoryProvisioningJobRepository,
    ProvisioningService,
)


@pytest.fixture
def repo():
    return InMemoryProvisioningJobRepository()


@pytest.fixture
def service(repo):
    return ProvisioningService(repo)


# ── Idempotency key required ────────────────────────────────────────


class TestIdempotencyKeyRequired:
    @pytest.mark.asyncio
    async def test_empty_key_raises(self, service):
        with pytest.raises(IdempotencyKeyRequired):
            await service.create_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='',
                created_by='user_1',
            )

    @pytest.mark.asyncio
    async def test_blank_key_raises(self, service):
        with pytest.raises(IdempotencyKeyRequired):
            await service.create_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='   ',
                created_by='user_1',
            )

    @pytest.mark.asyncio
    async def test_retry_empty_key_raises(self, service):
        with pytest.raises(IdempotencyKeyRequired):
            await service.retry_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='',
                created_by='user_1',
            )

    @pytest.mark.asyncio
    async def test_retry_blank_key_raises(self, service):
        with pytest.raises(IdempotencyKeyRequired):
            await service.retry_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='   ',
                created_by='user_1',
            )


# ── Happy path create ────────────────────────────────────────────────


class TestCreateProvisioningJob:
    @pytest.mark.asyncio
    async def test_creates_queued_job(self, service):
        result = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='create-1',
            created_by='user_1',
        )
        assert result.created is True
        assert result.job.workspace_id == 'ws_abc'
        assert result.job.state == 'queued'
        assert result.job.idempotency_key == 'create-1'
        assert result.job.attempt == 1
        assert result.job.id >= 1

    @pytest.mark.asyncio
    async def test_assigns_request_id(self, service):
        result = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='create-2',
            created_by='user_1',
            request_id='req-xyz',
        )
        assert result.job.request_id == 'req-xyz'


# ── Idempotency dedup ───────────────────────────────────────────────


class TestIdempotencyDedup:
    @pytest.mark.asyncio
    async def test_same_key_returns_existing(self, service):
        first = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        assert first.created is True

        second = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        assert second.created is False
        assert second.job.id == first.job.id

    @pytest.mark.asyncio
    async def test_same_key_third_call_still_deduped(self, service):
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        third = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        assert third.created is False

    @pytest.mark.asyncio
    async def test_different_workspace_same_key_is_separate(
        self, service,
    ):
        r1 = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        r2 = await service.create_provisioning_job(
            workspace_id='ws_def',
            idempotency_key='key-1',
            created_by='user_1',
        )
        assert r1.created is True
        assert r2.created is True
        assert r1.job.id != r2.job.id

    @pytest.mark.asyncio
    async def test_retry_same_key_returns_existing(self, service):
        first = await service.retry_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='retry-1',
            created_by='user_1',
        )
        second = await service.retry_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='retry-1',
            created_by='user_1',
        )
        assert first.created is True
        assert second.created is False
        assert second.job.id == first.job.id


# ── Single-active-job enforcement ────────────────────────────────────


class TestSingleActiveJob:
    @pytest.mark.asyncio
    async def test_second_create_raises_conflict(self, service):
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        with pytest.raises(ActiveJobConflict) as exc_info:
            await service.create_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='key-2',
                created_by='user_1',
            )
        assert exc_info.value.workspace_id == 'ws_abc'

    @pytest.mark.asyncio
    async def test_retry_raises_when_active_exists(self, service):
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        with pytest.raises(ActiveJobConflict):
            await service.retry_provisioning_job(
                workspace_id='ws_abc',
                idempotency_key='retry-1',
                created_by='user_1',
            )

    @pytest.mark.asyncio
    async def test_terminal_job_allows_new_create(self, service, repo):
        result = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        # Simulate the job reaching terminal error state.
        result.job.state = 'error'

        # New job with different key should succeed.
        r2 = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-2',
            created_by='user_1',
        )
        assert r2.created is True
        assert r2.job.id != result.job.id

    @pytest.mark.asyncio
    async def test_terminal_ready_allows_retry(self, service, repo):
        result = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        # Simulate job completing.
        result.job.state = 'ready'

        r2 = await service.retry_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='retry-1',
            created_by='user_1',
        )
        assert r2.created is True

    @pytest.mark.asyncio
    async def test_different_workspaces_independent(self, service):
        r1 = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        r2 = await service.create_provisioning_job(
            workspace_id='ws_def',
            idempotency_key='key-1',
            created_by='user_1',
        )
        assert r1.created is True
        assert r2.created is True


# ── Result type ──────────────────────────────────────────────────────


class TestCreateJobResult:
    @pytest.mark.asyncio
    async def test_result_is_frozen(self, service):
        result = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        with pytest.raises(AttributeError):
            result.created = False


# ── InMemoryRepo ─────────────────────────────────────────────────────


class TestInMemoryRepo:
    @pytest.mark.asyncio
    async def test_auto_increments_ids(self, repo):
        from control_plane.app.provisioning.job_service import (
            ProvisioningJobRecord,
        )

        r1 = await repo.create(ProvisioningJobRecord(
            id=0, workspace_id='ws_1', state='queued',
            attempt=1, idempotency_key='a',
        ))
        r2 = await repo.create(ProvisioningJobRecord(
            id=0, workspace_id='ws_2', state='queued',
            attempt=1, idempotency_key='b',
        ))
        assert r1.id == 1
        assert r2.id == 2

    @pytest.mark.asyncio
    async def test_get_active_returns_none_when_empty(self, repo):
        assert await repo.get_active_for_workspace('ws_x') is None

    @pytest.mark.asyncio
    async def test_get_by_key_returns_none_when_empty(self, repo):
        result = await repo.get_by_idempotency_key('ws_x', 'k')
        assert result is None
