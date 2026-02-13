"""Integration tests for SupabaseMemberRepository against real Supabase.

Bead: bd-1joj.5 (DB2)

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from control_plane.app.db.errors import SupabaseConflictError
from control_plane.app.db.supabase_client import SupabaseClient
from control_plane.app.db.member_repo import SupabaseMemberRepository


def _skip_without_creds():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        pytest.skip("SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set")
    return url, key


@pytest.mark.asyncio
async def test_real_invite_accept_list_remove_roundtrip():
    url, key = _skip_without_creds()
    async with httpx.AsyncClient() as http:
        client = SupabaseClient(supabase_url=url, service_role_key=key, http_client=http)
        member_repo = SupabaseMemberRepository(client)

        # Create a workspace first (needed for FK)
        owner_id = str(uuid.uuid4())
        ws = await client.insert("cloud.workspaces", {
            "name": "DB2 member test",
            "owner_id": owner_id,
        })
        ws_id = ws[0]["id"]

        try:
            email = f"test-{uuid.uuid4().hex[:8]}@example.com"
            user_id = str(uuid.uuid4())

            # 1. Invite
            member = await member_repo.add_member(ws_id, {"email": email})
            assert member["status"] == "pending"
            assert member["role"] == "admin"
            member_id = member["id"]

            # 2. Auto-accept
            activated = await member_repo.auto_accept_pending(user_id, email)
            assert len(activated) == 1
            assert activated[0]["status"] == "active"
            assert activated[0]["user_id"] == user_id

            # 3. Get membership
            membership = await member_repo.get_membership(ws_id, user_id)
            assert membership is not None
            assert membership["status"] == "active"

            # 4. List members
            members = await member_repo.list_members(ws_id)
            assert any(m["id"] == member_id for m in members)

            # 5. Remove (soft)
            removed = await member_repo.remove_member(ws_id, member_id)
            assert removed is True

            # 6. After removal, membership returns None
            membership_after = await member_repo.get_membership(ws_id, user_id)
            assert membership_after is None

            # 7. List no longer includes removed member
            members_after = await member_repo.list_members(ws_id)
            assert not any(m["id"] == member_id for m in members_after)

            # 8. Re-invite works after removal
            reinvite = await member_repo.add_member(ws_id, {"email": email})
            assert reinvite["status"] == "pending"

        finally:
            # Cleanup (CASCADE deletes members)
            await client.delete("cloud.workspaces", filters={"id": ("eq", ws_id)})


@pytest.mark.asyncio
async def test_real_duplicate_pending_invite_blocked():
    url, key = _skip_without_creds()
    async with httpx.AsyncClient() as http:
        client = SupabaseClient(supabase_url=url, service_role_key=key, http_client=http)
        member_repo = SupabaseMemberRepository(client)

        owner_id = str(uuid.uuid4())
        ws = await client.insert("cloud.workspaces", {
            "name": "DB2 dup test",
            "owner_id": owner_id,
        })
        ws_id = ws[0]["id"]

        try:
            email = f"dup-{uuid.uuid4().hex[:8]}@example.com"

            # First invite: OK
            await member_repo.add_member(ws_id, {"email": email})

            # Second invite for same email: 409
            with pytest.raises(SupabaseConflictError):
                await member_repo.add_member(ws_id, {"email": email})

        finally:
            await client.delete("cloud.workspaces", filters={"id": ("eq", ws_id)})
