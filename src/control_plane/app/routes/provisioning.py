"""Provisioning runtime status, retry, and events API.

Bead: bd-223o.10.5 (D5)

Exposes workspace provisioning state to the frontend onboarding flow:
  GET  /api/v1/workspaces/{workspace_id}/runtime  → current runtime status
  POST /api/v1/workspaces/{workspace_id}/retry     → trigger provisioning retry
  GET  /api/v1/workspaces/{workspace_id}/provision/events → step event log

Response contracts:
  - ``runtime`` includes state, step, attempt, last_error_code, last_error_detail,
    request_id, started_at, and finished_at for full UI traceability.
  - ``retry`` creates a new provisioning job (or deduplicates) and returns
    the resulting runtime snapshot.
  - ``events`` returns an ordered list of state transitions for the
    active or most-recent job.

All endpoints require authentication via ``get_auth_identity``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from control_plane.app.provisioning.job_service import (
    ActiveJobConflict,
    IdempotencyKeyRequired,
    ProvisioningJobRecord,
    ProvisioningJobRepository,
    ProvisioningService,
)
from control_plane.app.provisioning.state_machine import ACTIVE_STATES
from control_plane.app.security.auth_guard import get_auth_identity
from control_plane.app.security.token_verify import AuthIdentity


# ── Event log protocol ────────────────────────────────────────────────


class ProvisioningEventRecord:
    """Represents a single state-transition event."""

    __slots__ = ('job_id', 'from_state', 'to_state', 'timestamp', 'detail')

    def __init__(
        self,
        *,
        job_id: int,
        from_state: str,
        to_state: str,
        timestamp: datetime,
        detail: str = '',
    ) -> None:
        self.job_id = job_id
        self.from_state = from_state
        self.to_state = to_state
        self.timestamp = timestamp
        self.detail = detail


class ProvisioningEventRepository(Protocol):
    """Abstract event log storage for provisioning step transitions."""

    async def list_events_for_workspace(
        self, workspace_id: str, *, limit: int = 50,
    ) -> list[ProvisioningEventRecord]: ...


# ── In-memory event repository (for testing) ──────────────────────────


class InMemoryProvisioningEventRepository:
    """In-memory event log for testing."""

    def __init__(self) -> None:
        self._events: list[ProvisioningEventRecord] = []

    def append(self, event: ProvisioningEventRecord) -> None:
        self._events.append(event)

    async def list_events_for_workspace(
        self, workspace_id: str, *, limit: int = 50,
    ) -> list[ProvisioningEventRecord]:
        # In a real implementation, events would be filtered by workspace_id
        # via a join on the job table. For the in-memory store, return all
        # events (tests control what is inserted).
        return self._events[-limit:]


# ── Request schemas ───────────────────────────────────────────────────


class RetryRequest(BaseModel):
    idempotency_key: str | None = Field(
        default=None,
        description=(
            'Client-generated idempotency key. Auto-generated if omitted.'
        ),
    )


# ── Response helpers ──────────────────────────────────────────────────


def _runtime_response(job: ProvisioningJobRecord) -> dict:
    """Build a runtime status payload from a job record."""
    return {
        'state': job.state,
        'step': job.state if job.state in ACTIVE_STATES else None,
        'attempt': job.attempt,
        'request_id': job.request_id,
        'last_error_code': job.last_error_code,
        'last_error_detail': job.last_error_detail,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'finished_at': (
            job.finished_at.isoformat() if job.finished_at else None
        ),
        'created_at': job.created_at.isoformat(),
    }


def _event_response(event: ProvisioningEventRecord) -> dict:
    """Build an event payload from an event record."""
    return {
        'job_id': event.job_id,
        'from_state': event.from_state,
        'to_state': event.to_state,
        'timestamp': event.timestamp.isoformat(),
        'detail': event.detail,
    }


# ── Route factory ─────────────────────────────────────────────────────


def create_provisioning_router(
    job_repo: ProvisioningJobRepository,
    provisioning_service: ProvisioningService,
    event_repo: ProvisioningEventRepository | None = None,
) -> APIRouter:
    """Create provisioning status/retry/events router.

    Args:
        job_repo: Repository for querying provisioning jobs.
        provisioning_service: Service for creating/retrying jobs.
        event_repo: Optional event log repository. If None, the events
            endpoint returns an empty list.

    Returns:
        FastAPI router with provisioning runtime endpoints.
    """
    router = APIRouter(tags=['provisioning'])

    @router.get('/api/v1/workspaces/{workspace_id}/runtime')
    async def get_runtime_status(
        workspace_id: str,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Get current provisioning runtime status for a workspace.

        Returns the most recent job's state, step, attempt, error details,
        and request_id for UI and operations traceability.
        """
        # Look for an active job first.
        job = await job_repo.get_active_for_workspace(workspace_id)

        if job is None:
            # No active job — look for the most recent job (terminal).
            job = await _get_latest_job(job_repo, workspace_id)

        if job is None:
            return JSONResponse(
                status_code=404,
                content={
                    'error': 'no_provisioning_job',
                    'detail': (
                        f'No provisioning job found for workspace '
                        f'{workspace_id!r}.'
                    ),
                },
            )

        return _runtime_response(job)

    @router.post('/api/v1/workspaces/{workspace_id}/retry')
    async def retry_provisioning(
        workspace_id: str,
        body: RetryRequest | None = None,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """Retry provisioning for a workspace after an error.

        Generates an idempotency key if not provided. Returns the new
        or deduplicated job's runtime status.
        """
        idempotency_key = (
            body.idempotency_key
            if body and body.idempotency_key
            else f'retry-{uuid.uuid4().hex[:16]}'
        )

        try:
            result = await provisioning_service.retry_provisioning_job(
                workspace_id=workspace_id,
                idempotency_key=idempotency_key,
                created_by=identity.user_id,
                request_id=f'req-{uuid.uuid4().hex[:12]}',
            )
        except ActiveJobConflict as exc:
            return JSONResponse(
                status_code=409,
                content={
                    'error': 'active_job_conflict',
                    'detail': str(exc),
                    'active_job_id': exc.active_job_id,
                },
            )
        except IdempotencyKeyRequired:
            return JSONResponse(
                status_code=400,
                content={
                    'error': 'idempotency_key_required',
                    'detail': (
                        'idempotency_key is required for provisioning '
                        'requests'
                    ),
                },
            )

        return _runtime_response(result.job)

    @router.get('/api/v1/workspaces/{workspace_id}/provision/events')
    async def list_provision_events(
        workspace_id: str,
        limit: int = 50,
        identity: AuthIdentity = Depends(get_auth_identity),
    ):
        """List provisioning state-transition events for a workspace.

        Returns an ordered list of step transitions for the active or
        most recent provisioning job.
        """
        if event_repo is None:
            return {'events': []}

        events = await event_repo.list_events_for_workspace(
            workspace_id, limit=min(limit, 100),
        )
        return {
            'events': [_event_response(e) for e in events],
        }

    return router


# ── Internal helpers ──────────────────────────────────────────────────


async def _get_latest_job(
    repo: ProvisioningJobRepository,
    workspace_id: str,
) -> ProvisioningJobRecord | None:
    """Return the most recent job for a workspace (active or terminal).

    The ProvisioningJobRepository protocol only exposes active lookups
    and idempotency-key lookups. For the general "latest job" query we
    fall back to scanning the in-memory store (sufficient for the
    in-memory testing implementation). Production implementations will
    add a ``get_latest_for_workspace`` method to the repository.
    """
    # Check if the repo has a get_latest_for_workspace method (production).
    if hasattr(repo, 'get_latest_for_workspace'):
        return await repo.get_latest_for_workspace(workspace_id)

    # Fallback: scan in-memory jobs dict (InMemoryProvisioningJobRepository).
    if hasattr(repo, '_jobs'):
        matches = [
            j for j in repo._jobs.values()
            if j.workspace_id == workspace_id
        ]
        if matches:
            return max(matches, key=lambda j: j.id)

    return None
