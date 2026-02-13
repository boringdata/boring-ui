"""Supabase-backed provisioning job repository.

Bead: bd-1joj.9 (DB6)

Implements the JobRepository protocol using SupabaseClient for PostgREST
operations against the cloud.workspace_provision_jobs table.

Single-active-job and idempotency-key dedup are enforced by DB unique
partial indexes (ux_workspace_jobs_active, ux_workspace_jobs_idempotency)
applied in migration 002.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .errors import SupabaseConflictError
from .supabase_client import SupabaseClient

# States considered "active" (must match the partial index WHERE clause).
ACTIVE_STATES: frozenset[str] = frozenset({
    "queued",
    "release_resolve",
    "creating_sandbox",
    "uploading_artifact",
    "bootstrapping",
    "health_check",
})

TERMINAL_STATES: frozenset[str] = frozenset({"ready", "error"})

TABLE = "cloud.workspace_provision_jobs"


class SupabaseProvisioningJobRepository:
    """Provisioning job CRUD backed by Supabase PostgREST.

    Satisfies the ``JobRepository`` protocol from ``protocols.py``.
    """

    def __init__(self, client: SupabaseClient) -> None:
        self._client = client

    async def create_job(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert a new provisioning job.

        If a duplicate idempotency_key exists for the same workspace, returns
        the existing job instead of raising.

        Raises SupabaseConflictError if a non-idempotency 409 occurs (e.g.
        single-active-job constraint).
        """
        row: dict[str, Any] = {**data}
        row.setdefault("state", "queued")

        idempotency_key = row.get("idempotency_key")
        workspace_id = row.get("workspace_id")

        try:
            rows = await self._client.insert(TABLE, row)
            return rows[0]
        except SupabaseConflictError:
            # PostgREST 409 can come from either ux_workspace_jobs_active
            # (single-active-job) or ux_workspace_jobs_idempotency (dedup).
            # We cannot distinguish which index triggered the conflict, so
            # when an idempotency key is present, we attempt a SELECT to
            # check for the dedup case. If the SELECT returns a row, it was
            # an idempotency match. If empty, the conflict was the active-job
            # constraint and we re-raise.
            if idempotency_key and workspace_id:
                existing = await self._client.select(
                    TABLE,
                    filters={
                        "workspace_id": ("eq", workspace_id),
                        "idempotency_key": ("eq", idempotency_key),
                    },
                    limit=1,
                )
                if existing:
                    return existing[0]
            # Otherwise it's the single-active-job constraint; re-raise.
            raise

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        rows = await self._client.select(
            TABLE,
            filters={"id": ("eq", job_id)},
            limit=1,
        )
        return rows[0] if rows else None

    async def update_job(self, job_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        row: dict[str, Any] = {**data}
        row["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Auto-set finished_at when entering a terminal state, unless the
        # caller explicitly provides it. Note: started_at is NOT auto-set
        # because without read-before-write we cannot know if it was already
        # set in the DB; callers should set started_at explicitly when
        # picking up a job.
        state = row.get("state")
        if state in TERMINAL_STATES and "finished_at" not in row:
            row["finished_at"] = row["updated_at"]

        rows = await self._client.update(
            TABLE,
            filters={"id": ("eq", job_id)},
            data=row,
        )
        return rows[0] if rows else None

    async def get_active_job(self, workspace_id: str) -> dict[str, Any] | None:
        """Return the current active (non-terminal) job for a workspace, or None."""
        rows = await self._client.select(
            TABLE,
            filters={
                "workspace_id": ("eq", workspace_id),
                "state": ("in", list(ACTIVE_STATES)),
            },
            limit=1,
            order="created_at.desc",
        )
        return rows[0] if rows else None

    async def list_jobs(self, workspace_id: str) -> list[dict[str, Any]]:
        """List all provisioning jobs for a workspace (newest first)."""
        return await self._client.select(
            TABLE,
            filters={"workspace_id": ("eq", workspace_id)},
            order="created_at.desc",
        )
