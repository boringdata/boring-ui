"""Supabase-backed workspace runtime metadata store.

Bead: bd-1joj.9 (DB6)

Implements the RuntimeMetadataStore protocol using SupabaseClient for PostgREST
operations against the cloud.workspace_runtime table.

Runtime rows have a 1:1 relationship with workspaces (workspace_id is PK).
Upserts are implemented via PostgREST ``resolution=merge-duplicates``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .supabase_client import SupabaseClient

TABLE = "cloud.workspace_runtime"


class SupabaseRuntimeMetadataStore:
    """Workspace runtime metadata backed by Supabase PostgREST.

    Satisfies the ``RuntimeMetadataStore`` protocol from ``protocols.py``.
    """

    def __init__(self, client: SupabaseClient) -> None:
        self._client = client

    async def get_runtime(self, workspace_id: str) -> dict[str, Any] | None:
        rows = await self._client.select(
            TABLE,
            filters={"workspace_id": ("eq", workspace_id)},
            limit=1,
        )
        return rows[0] if rows else None

    async def upsert_runtime(self, workspace_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create or update the runtime row for a workspace.

        Uses PostgREST upsert (ON CONFLICT DO UPDATE) since workspace_id is PK.
        """
        row: dict[str, Any] = {**data, "workspace_id": workspace_id}
        row["updated_at"] = datetime.now(timezone.utc).isoformat()
        row.setdefault("app_id", "boring-ui")

        rows = await self._client.insert(TABLE, row, upsert=True)
        return rows[0]

    async def update_state(
        self,
        workspace_id: str,
        state: str,
        *,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> dict[str, Any] | None:
        """Convenience: update just the state and optional error fields."""
        update_data: dict[str, Any] = {
            "state": state,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if error_code is not None:
            update_data["last_error_code"] = error_code
        if error_detail is not None:
            update_data["last_error_detail"] = error_detail

        # Clear error fields when transitioning to a non-error state.
        if state != "error":
            update_data.setdefault("last_error_code", None)
            update_data.setdefault("last_error_detail", None)

        rows = await self._client.update(
            TABLE,
            filters={"workspace_id": ("eq", workspace_id)},
            data=update_data,
        )
        return rows[0] if rows else None
