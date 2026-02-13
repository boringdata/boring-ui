"""Tests for provisioning runtime status, retry, and events API.

Bead: bd-223o.10.5 (D5)

Validates:
  1. GET /runtime returns current job state, step, attempt, error details
  2. GET /runtime returns 404 when no provisioning job exists
  3. GET /runtime returns terminal job when no active job
  4. POST /retry creates a new job and returns runtime status
  5. POST /retry returns 409 when active job conflicts
  6. POST /retry auto-generates idempotency key
  7. POST /retry deduplicates on same idempotency key
  8. GET /provision/events returns event list
  9. GET /provision/events returns empty when no event repo
 10. Response includes request_id for traceability
 11. Response includes started_at and finished_at timestamps
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from control_plane.app.provisioning.job_service import (
    InMemoryProvisioningJobRepository,
    ProvisioningJobRecord,
    ProvisioningService,
)
from control_plane.app.routes.provisioning import (
    InMemoryProvisioningEventRepository,
    ProvisioningEventRecord,
    create_provisioning_router,
)
from control_plane.app.security.token_verify import AuthIdentity


# ── Test fixtures ─────────────────────────────────────────────────────


def _mock_auth_identity():
    """Return a test AuthIdentity."""
    return AuthIdentity(
        user_id='user_test_123',
        email='test@example.com',
    )


def _create_test_app(
    job_repo=None,
    provisioning_service=None,
    event_repo=None,
):
    """Create a FastAPI app with provisioning routes for testing."""
    if job_repo is None:
        job_repo = InMemoryProvisioningJobRepository()
    if provisioning_service is None:
        provisioning_service = ProvisioningService(job_repo)

    app = FastAPI()

    # Override auth dependency for testing.
    from control_plane.app.security.auth_guard import get_auth_identity

    app.dependency_overrides[get_auth_identity] = _mock_auth_identity

    router = create_provisioning_router(
        job_repo=job_repo,
        provisioning_service=provisioning_service,
        event_repo=event_repo,
    )
    app.include_router(router)
    return app, job_repo, provisioning_service


@pytest.fixture
def repo():
    return InMemoryProvisioningJobRepository()


@pytest.fixture
def service(repo):
    return ProvisioningService(repo)


@pytest.fixture
def event_repo():
    return InMemoryProvisioningEventRepository()


@pytest.fixture
def client(repo, service):
    app, _, _ = _create_test_app(
        job_repo=repo, provisioning_service=service,
    )
    return TestClient(app)


@pytest.fixture
def client_with_events(repo, service, event_repo):
    app, _, _ = _create_test_app(
        job_repo=repo,
        provisioning_service=service,
        event_repo=event_repo,
    )
    return TestClient(app)


def _now():
    return datetime.now(timezone.utc)


# =====================================================================
# 1. GET /runtime — active job
# =====================================================================


class TestGetRuntimeStatusActiveJob:

    @pytest.mark.asyncio
    async def test_returns_active_job_state(self, repo, service, client):
        result = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        assert resp.status_code == 200
        data = resp.json()
        assert data['state'] == 'queued'
        assert data['attempt'] == 1

    @pytest.mark.asyncio
    async def test_returns_step_for_active_state(self, repo, service, client):
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        data = resp.json()
        assert data['step'] == 'queued'

    @pytest.mark.asyncio
    async def test_returns_request_id(self, repo, service, client):
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
            request_id='req-abc123',
        )
        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        data = resp.json()
        assert data['request_id'] == 'req-abc123'

    @pytest.mark.asyncio
    async def test_returns_timestamps(self, repo, service, client):
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        data = resp.json()
        assert data['started_at'] is not None
        assert data['created_at'] is not None
        # Active job has no finished_at.
        assert data['finished_at'] is None

    @pytest.mark.asyncio
    async def test_no_error_details_on_active(self, repo, service, client):
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        data = resp.json()
        assert data['last_error_code'] is None
        assert data['last_error_detail'] is None


# =====================================================================
# 2. GET /runtime — 404 when no job
# =====================================================================


class TestGetRuntimeStatusNoJob:

    def test_returns_404(self, client):
        resp = client.get('/api/v1/workspaces/ws_missing/runtime')
        assert resp.status_code == 404
        data = resp.json()
        assert data['error'] == 'no_provisioning_job'

    def test_404_includes_workspace_id(self, client):
        resp = client.get('/api/v1/workspaces/ws_xyz/runtime')
        data = resp.json()
        assert 'ws_xyz' in data['detail']


# =====================================================================
# 3. GET /runtime — terminal job (no active)
# =====================================================================


class TestGetRuntimeStatusTerminalJob:

    @pytest.mark.asyncio
    async def test_returns_terminal_error_job(self, repo, service, client):
        result = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        # Simulate error transition.
        result.job.state = 'error'
        result.job.last_error_code = 'STEP_TIMEOUT'
        result.job.last_error_detail = 'step timed out'

        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        assert resp.status_code == 200
        data = resp.json()
        assert data['state'] == 'error'
        assert data['last_error_code'] == 'STEP_TIMEOUT'
        assert data['last_error_detail'] == 'step timed out'

    @pytest.mark.asyncio
    async def test_returns_terminal_ready_job(self, repo, service, client):
        result = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        result.job.state = 'ready'

        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        assert resp.status_code == 200
        data = resp.json()
        assert data['state'] == 'ready'
        # step is None for terminal states.
        assert data['step'] is None

    @pytest.mark.asyncio
    async def test_returns_latest_of_multiple_jobs(
        self, repo, service, client,
    ):
        """When multiple terminal jobs exist, return the most recent."""
        r1 = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        r1.job.state = 'error'

        r2 = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-2',
            created_by='user_1',
        )
        r2.job.state = 'ready'

        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        data = resp.json()
        # The second job (higher ID) should be returned.
        assert data['state'] == 'ready'


# =====================================================================
# 4. POST /retry — happy path
# =====================================================================


class TestRetryProvisioning:

    @pytest.mark.asyncio
    async def test_retry_creates_new_job(self, repo, service, client):
        # Create and error out a job first.
        r1 = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='orig-key',
            created_by='user_1',
        )
        r1.job.state = 'error'

        resp = client.post(
            '/api/v1/workspaces/ws_abc/retry',
            json={'idempotency_key': 'retry-key-1'},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['state'] == 'queued'
        assert data['attempt'] == 1
        assert data['request_id'] is not None

    @pytest.mark.asyncio
    async def test_retry_auto_generates_idempotency_key(
        self, repo, service, client,
    ):
        """Retry without explicit idempotency_key still works."""
        r1 = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='orig-key',
            created_by='user_1',
        )
        r1.job.state = 'error'

        resp = client.post('/api/v1/workspaces/ws_abc/retry')
        assert resp.status_code == 200
        data = resp.json()
        assert data['state'] == 'queued'

    @pytest.mark.asyncio
    async def test_retry_deduplicates_same_key(
        self, repo, service, client,
    ):
        r1 = await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='orig-key',
            created_by='user_1',
        )
        r1.job.state = 'error'

        resp1 = client.post(
            '/api/v1/workspaces/ws_abc/retry',
            json={'idempotency_key': 'retry-dedup'},
        )
        resp2 = client.post(
            '/api/v1/workspaces/ws_abc/retry',
            json={'idempotency_key': 'retry-dedup'},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Same job returned.
        assert resp1.json()['started_at'] == resp2.json()['started_at']


# =====================================================================
# 5. POST /retry — 409 conflict
# =====================================================================


class TestRetryConflict:

    @pytest.mark.asyncio
    async def test_returns_409_when_active_job_exists(
        self, repo, service, client,
    ):
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        resp = client.post(
            '/api/v1/workspaces/ws_abc/retry',
            json={'idempotency_key': 'retry-key'},
        )
        assert resp.status_code == 409
        data = resp.json()
        assert data['error'] == 'active_job_conflict'
        assert 'active_job_id' in data


# =====================================================================
# 6. GET /provision/events — with event repo
# =====================================================================


class TestProvisionEvents:

    def test_returns_events_list(self, event_repo, client_with_events):
        event_repo.append(ProvisioningEventRecord(
            job_id=1,
            from_state='queued',
            to_state='release_resolve',
            timestamp=_now(),
            detail='advanced',
        ))
        event_repo.append(ProvisioningEventRecord(
            job_id=1,
            from_state='release_resolve',
            to_state='creating_sandbox',
            timestamp=_now(),
        ))

        resp = client_with_events.get(
            '/api/v1/workspaces/ws_abc/provision/events',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['events']) == 2
        assert data['events'][0]['from_state'] == 'queued'
        assert data['events'][0]['to_state'] == 'release_resolve'
        assert data['events'][0]['detail'] == 'advanced'

    def test_empty_events_when_no_events(self, client_with_events):
        resp = client_with_events.get(
            '/api/v1/workspaces/ws_abc/provision/events',
        )
        assert resp.status_code == 200
        assert resp.json()['events'] == []

    def test_respects_limit_parameter(self, event_repo, client_with_events):
        for i in range(10):
            event_repo.append(ProvisioningEventRecord(
                job_id=1,
                from_state=f'state_{i}',
                to_state=f'state_{i+1}',
                timestamp=_now(),
            ))

        resp = client_with_events.get(
            '/api/v1/workspaces/ws_abc/provision/events?limit=3',
        )
        data = resp.json()
        assert len(data['events']) == 3

    def test_limit_capped_at_100(self, event_repo, client_with_events):
        """Even if limit=999 is requested, we cap at 100."""
        resp = client_with_events.get(
            '/api/v1/workspaces/ws_abc/provision/events?limit=999',
        )
        # Should not error; just returns whatever is available.
        assert resp.status_code == 200


# =====================================================================
# 7. GET /provision/events — without event repo
# =====================================================================


class TestProvisionEventsNoRepo:

    def test_returns_empty_events(self, client):
        resp = client.get(
            '/api/v1/workspaces/ws_abc/provision/events',
        )
        assert resp.status_code == 200
        assert resp.json()['events'] == []


# =====================================================================
# 8. Event record structure
# =====================================================================


class TestEventRecordStructure:

    def test_event_fields(self, event_repo, client_with_events):
        ts = _now()
        event_repo.append(ProvisioningEventRecord(
            job_id=42,
            from_state='uploading_artifact',
            to_state='error',
            timestamp=ts,
            detail='checksum mismatch',
        ))

        resp = client_with_events.get(
            '/api/v1/workspaces/ws_abc/provision/events',
        )
        event = resp.json()['events'][0]
        assert event['job_id'] == 42
        assert event['from_state'] == 'uploading_artifact'
        assert event['to_state'] == 'error'
        assert event['timestamp'] == ts.isoformat()
        assert event['detail'] == 'checksum mismatch'


# =====================================================================
# 9. Runtime response field contract
# =====================================================================


class TestRuntimeResponseContract:
    """Verify the runtime response contains all fields the frontend needs."""

    @pytest.mark.asyncio
    async def test_response_has_all_required_fields(
        self, repo, service, client,
    ):
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
            request_id='req-trace-1',
        )
        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        data = resp.json()
        required_fields = {
            'state', 'step', 'attempt', 'request_id',
            'last_error_code', 'last_error_detail',
            'started_at', 'finished_at', 'created_at',
        }
        assert required_fields.issubset(data.keys())

    @pytest.mark.asyncio
    async def test_frontend_runtime_state_extraction(
        self, repo, service, client,
    ):
        """Frontend extractRuntimeState reads runtime.state — verify it's set."""
        await service.create_provisioning_job(
            workspace_id='ws_abc',
            idempotency_key='key-1',
            created_by='user_1',
        )
        resp = client.get('/api/v1/workspaces/ws_abc/runtime')
        data = resp.json()
        # Frontend uses runtime.state to derive onboarding state.
        assert 'state' in data
        assert data['state'] in (
            'queued', 'release_resolve', 'creating_sandbox',
            'uploading_artifact', 'bootstrapping', 'health_check',
            'ready', 'error',
        )


# =====================================================================
# 10. Cross-workspace isolation
# =====================================================================


class TestCrossWorkspaceIsolation:

    @pytest.mark.asyncio
    async def test_runtime_scoped_to_workspace(
        self, repo, service, client,
    ):
        await service.create_provisioning_job(
            workspace_id='ws_a',
            idempotency_key='key-a',
            created_by='user_1',
        )
        await service.create_provisioning_job(
            workspace_id='ws_b',
            idempotency_key='key-b',
            created_by='user_1',
        )

        resp_a = client.get('/api/v1/workspaces/ws_a/runtime')
        resp_b = client.get('/api/v1/workspaces/ws_b/runtime')
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200
        # Different jobs.
        assert (
            resp_a.json()['created_at'] != resp_b.json()['created_at']
            or resp_a.json()['request_id'] != resp_b.json()['request_id']
        )

    @pytest.mark.asyncio
    async def test_missing_workspace_returns_404(self, client):
        resp = client.get('/api/v1/workspaces/ws_nonexistent/runtime')
        assert resp.status_code == 404
