"""Supabase-backed WorkspaceRepository implementation.

Bead: bd-1joj.4 (DB1)

Implements the WorkspaceRepository protocol using the SupabaseClient (DB0)
to persist workspaces in cloud.workspaces via PostgREST.
"""

from __future__ import annotations

from typing import Any

from .supabase_client import SupabaseClient


class SupabaseWorkspaceRepository:
    """WorkspaceRepository backed by cloud.workspaces via PostgREST."""

    TABLE = "cloud.workspaces"
    MEMBERS_TABLE = "cloud.workspace_members"
    DEFAULT_APP_ID = "boring-ui"

    def __init__(self, client: SupabaseClient) -> None:
        self._client = client

    async def get(self, workspace_id: str) -> dict[str, Any] | None:
        rows = await self._client.select(
            self.TABLE,
            filters={"id": ("eq", workspace_id)},
            limit=1,
        )
        return rows[0] if rows else None

    async def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        # Two-query approach: get workspace IDs from active memberships,
        # then fetch the workspace rows. PostgREST resource embedding with
        # non-public schemas can be fragile, so this is intentionally simple.
        members = await self._client.select(
            self.MEMBERS_TABLE,
            filters={
                "user_id": ("eq", user_id),
                "status": ("eq", "active"),
            },
            columns="workspace_id",
        )
        if not members:
            return []
        ws_ids = [m["workspace_id"] for m in members]
        return await self._client.select(
            self.TABLE,
            filters={"id": ("in", ws_ids)},
            order="created_at.desc",
        )

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        row = {**data}
        row.setdefault("app_id", self.DEFAULT_APP_ID)
        rows = await self._client.insert(self.TABLE, row)
        return rows[0]

    async def update(
        self, workspace_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        rows = await self._client.update(
            self.TABLE,
            filters={"id": ("eq", workspace_id)},
            data=data,
        )
        return rows[0] if rows else None
