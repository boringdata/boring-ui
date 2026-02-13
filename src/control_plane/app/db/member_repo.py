"""Supabase-backed MemberRepository implementation.

Bead: bd-1joj.5 (DB2)

Implements the MemberRepository protocol using the SupabaseClient (DB0)
to persist workspace memberships in cloud.workspace_members via PostgREST.

Key behaviors:
  - invite (add_member) inserts with status='pending', role='admin' (V0)
  - Duplicate pending invites rejected by DB unique partial index (409)
  - remove_member sets status='removed' (soft removal, never hard delete)
  - auto_accept_pending binds user_id and sets status='active' by email match
"""

from __future__ import annotations

from typing import Any

from .errors import SupabaseConflictError
from .supabase_client import SupabaseClient


class SupabaseMemberRepository:
    """MemberRepository backed by cloud.workspace_members via PostgREST."""

    TABLE = "cloud.workspace_members"

    def __init__(self, client: SupabaseClient) -> None:
        self._client = client

    async def list_members(self, workspace_id: str) -> list[dict[str, Any]]:
        return await self._client.select(
            self.TABLE,
            filters={
                "workspace_id": ("eq", workspace_id),
                "status": ("neq", "removed"),
            },
            order="created_at.asc",
        )

    async def add_member(
        self, workspace_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        row = {
            "workspace_id": workspace_id,
            "status": "pending",
            "role": "admin",  # V0: admin only
            **data,
        }
        # The DB unique partial index ux_workspace_members_email prevents
        # duplicate (workspace_id, lower(email)) WHERE status IN ('pending', 'active').
        # PostgREST returns 409 on conflict → SupabaseConflictError.
        rows = await self._client.insert(self.TABLE, row)
        return rows[0]

    async def remove_member(
        self, workspace_id: str, member_id: str
    ) -> bool:
        rows = await self._client.update(
            self.TABLE,
            filters={
                "workspace_id": ("eq", workspace_id),
                "id": ("eq", member_id),
            },
            data={"status": "removed"},
        )
        return len(rows) > 0

    async def get_membership(
        self, workspace_id: str, user_id: str
    ) -> dict[str, Any] | None:
        rows = await self._client.select(
            self.TABLE,
            filters={
                "workspace_id": ("eq", workspace_id),
                "user_id": ("eq", user_id),
                "status": ("eq", "active"),
            },
            limit=1,
        )
        return rows[0] if rows else None

    async def auto_accept_pending(
        self, user_id: str, email: str
    ) -> list[dict[str, Any]]:
        """Activate all pending invites for this email and bind the user_id.

        Called during workspace listing (section 13.4) to auto-accept
        invites when the user's email matches a pending membership.

        Returns the list of activated membership rows.
        """
        # Find all pending invites for this email (case-insensitive).
        # PostgREST ilike handles case-insensitive matching.
        pending = await self._client.select(
            self.TABLE,
            filters={
                "email": ("ilike", email),
                "status": ("eq", "pending"),
            },
        )
        if not pending:
            return []

        activated: list[dict[str, Any]] = []
        for member in pending:
            rows = await self._client.update(
                self.TABLE,
                filters={"id": ("eq", member["id"])},
                data={"status": "active", "user_id": user_id},
            )
            if rows:
                activated.extend(rows)
        return activated
