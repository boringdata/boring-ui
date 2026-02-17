"""Provisioning job service with idempotency and single-active-job enforcement.

Bead: bd-223o.10.3 (D3)

Enforces three invariants:
  1. Every provisioning request requires a non-empty ``idempotency_key``.
  2. At most one active (non-terminal) provisioning job per workspace.
  3. Duplicate ``idempotency_key`` for the same workspace returns the existing
     job without creating a new one.

The database schema (002_v0_core_schema.sql) provides matching unique partial
indexes as a safety net, but this module enforces the rules at the application
layer for clear error semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from .state_machine import ACTIVE_STATES

# ── Error types ──────────────────────────────────────────────────────


class IdempotencyKeyRequired(ValueError):
    """Raised when idempotency_key is missing or blank."""

    def __init__(self) -> None:
        super().__init__(
            'idempotency_key is required for provisioning requests'
        )


class ActiveJobConflict(Exception):
    """Raised when a workspace already has an active provisioning job."""

    def __init__(self, workspace_id: str, active_job_id: int) -> None:
        self.workspace_id = workspace_id
        self.active_job_id = active_job_id
        super().__init__(
            f'workspace {workspace_id!r} already has active '
            f'provisioning job {active_job_id}'
        )


# ── Domain record ────────────────────────────────────────────────────


@dataclass
class ProvisioningJobRecord:
    """Row-level representation aligned with cloud.workspace_provision_jobs."""

    id: int
    workspace_id: str
    state: str
    attempt: int
    idempotency_key: str
    request_id: str | None = None
    modal_call_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_error_code: str | None = None
    last_error_detail: str | None = None
    created_by: str = ''
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Repository protocol ─────────────────────────────────────────────


class ProvisioningJobRepository(Protocol):
    """Abstract storage for provisioning jobs.

    Implementations: InMemoryProvisioningJobRepository (testing),
    SupabaseProvisioningJobRepository (production).
    """

    async def create(
        self, record: ProvisioningJobRecord,
    ) -> ProvisioningJobRecord:
        """Persist a new job record and assign an ID."""
        ...

    async def get_active_for_workspace(
        self, workspace_id: str,
    ) -> ProvisioningJobRecord | None:
        """Return the single active job for a workspace, or None."""
        ...

    async def get_by_idempotency_key(
        self, workspace_id: str, idempotency_key: str,
    ) -> ProvisioningJobRecord | None:
        """Return existing job matching workspace + idempotency_key."""
        ...


# ── In-memory implementation ────────────────────────────────────────


class InMemoryProvisioningJobRepository:
    """In-memory job repository for testing.

    Mirrors DB unique index behavior:
      - ux_workspace_jobs_active → at most one active job per workspace
      - ux_workspace_jobs_idempotency → unique (workspace, idempotency_key)
    """

    def __init__(self) -> None:
        self._jobs: dict[int, ProvisioningJobRecord] = {}
        self._next_id: int = 1

    async def create(
        self, record: ProvisioningJobRecord,
    ) -> ProvisioningJobRecord:
        record.id = self._next_id
        self._next_id += 1
        self._jobs[record.id] = record
        return record

    async def get_active_for_workspace(
        self, workspace_id: str,
    ) -> ProvisioningJobRecord | None:
        for job in self._jobs.values():
            if (
                job.workspace_id == workspace_id
                and job.state in ACTIVE_STATES
            ):
                return job
        return None

    async def get_by_idempotency_key(
        self, workspace_id: str, idempotency_key: str,
    ) -> ProvisioningJobRecord | None:
        for job in self._jobs.values():
            if (
                job.workspace_id == workspace_id
                and job.idempotency_key == idempotency_key
            ):
                return job
        return None


# ── Service result ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CreateJobResult:
    """Result of a provisioning create/retry request.

    ``created`` is True when a new job was inserted, False when an
    existing job was returned via idempotency dedup.
    """

    created: bool
    job: ProvisioningJobRecord


# ── Service ──────────────────────────────────────────────────────────


class ProvisioningService:
    """Orchestrates provisioning job creation with D3 invariants.

    Invariants enforced:
      1. idempotency_key is required (non-empty string).
      2. At most one active job per workspace (single-active-job).
      3. Same (workspace_id, idempotency_key) returns existing job.
    """

    def __init__(self, repo: ProvisioningJobRepository) -> None:
        self._repo = repo

    async def create_provisioning_job(
        self,
        *,
        workspace_id: str,
        idempotency_key: str,
        created_by: str,
        request_id: str | None = None,
    ) -> CreateJobResult:
        """Create a new provisioning job or return idempotent match.

        Raises:
            IdempotencyKeyRequired: If idempotency_key is missing/blank.
            ActiveJobConflict: If workspace already has an active job.
        """
        _require_idempotency_key(idempotency_key)

        # Idempotency check: return existing if same key was already used.
        existing = await self._repo.get_by_idempotency_key(
            workspace_id, idempotency_key,
        )
        if existing is not None:
            return CreateJobResult(created=False, job=existing)

        # Single-active-job enforcement.
        active = await self._repo.get_active_for_workspace(workspace_id)
        if active is not None:
            raise ActiveJobConflict(workspace_id, active.id)

        now = datetime.now(timezone.utc)
        record = ProvisioningJobRecord(
            id=0,
            workspace_id=workspace_id,
            state='queued',
            attempt=1,
            idempotency_key=idempotency_key,
            request_id=request_id,
            created_by=created_by,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        created = await self._repo.create(record)
        return CreateJobResult(created=True, job=created)

    async def retry_provisioning_job(
        self,
        *,
        workspace_id: str,
        idempotency_key: str,
        created_by: str,
        request_id: str | None = None,
    ) -> CreateJobResult:
        """Create a retry job after a previous error.

        Same invariants as create: idempotency_key required, no active
        job may exist (the previous error'd job is terminal and does
        not count as active).

        Raises:
            IdempotencyKeyRequired: If idempotency_key is missing/blank.
            ActiveJobConflict: If workspace already has an active job.
        """
        _require_idempotency_key(idempotency_key)

        existing = await self._repo.get_by_idempotency_key(
            workspace_id, idempotency_key,
        )
        if existing is not None:
            return CreateJobResult(created=False, job=existing)

        active = await self._repo.get_active_for_workspace(workspace_id)
        if active is not None:
            raise ActiveJobConflict(workspace_id, active.id)

        now = datetime.now(timezone.utc)
        record = ProvisioningJobRecord(
            id=0,
            workspace_id=workspace_id,
            state='queued',
            attempt=1,
            idempotency_key=idempotency_key,
            request_id=request_id,
            created_by=created_by,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        created = await self._repo.create(record)
        return CreateJobResult(created=True, job=created)


def _require_idempotency_key(key: str) -> None:
    """Validate that idempotency_key is present and non-blank."""
    if not key or not key.strip():
        raise IdempotencyKeyRequired()
