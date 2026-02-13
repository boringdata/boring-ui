"""Tests for pending invite auto-accept on workspace list load.

Bead: bd-223o.9.3 (C3)

Validates:
  - Pending invites auto-accepted on first workspace list load
  - Auto-accepted workspaces appear in the list response
  - Case-insensitive email matching
  - Already-active invites are idempotent (not double-accepted)
  - Removed invites are not auto-accepted
  - Only matching email invites are accepted
"""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from control_plane.app.routes.members import (
    InMemoryMemberRepository,
    Member,
)
from control_plane.app.routes.workspaces import (
    InMemoryWorkspaceRepository,
    Workspace,
    create_workspace_router,
)
from control_plane.app.security.auth_guard import AuthGuardMiddleware
from control_plane.app.security.token_verify import (
    StaticKeyProvider,
    TokenVerifier,
)

# ── Test constants ────────────────────────────────────────────────────

TEST_SECRET = 'test-auto-accept-secret'
TEST_AUDIENCE = 'authenticated'


def _make_token(
    user_id: str = 'invitee-uuid',
    email: str = 'invitee@example.com',
) -> str:
    payload = {
        'sub': user_id,
        'email': email,
        'role': 'authenticated',
        'aud': TEST_AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    return jwt.encode(payload, TEST_SECRET, algorithm='HS256')


def _auth_headers(
    user_id: str = 'invitee-uuid',
    email: str = 'invitee@example.com',
) -> dict:
    return {'Authorization': f'Bearer {_make_token(user_id=user_id, email=email)}'}


async def _setup_workspace_with_invite(
    ws_repo: InMemoryWorkspaceRepository,
    member_repo: InMemoryMemberRepository,
    email: str = 'invitee@example.com',
    workspace_name: str = 'Invited WS',
    ws_id: str = 'ws_invited',
) -> str:
    """Create a workspace owned by someone else and add a pending invite."""
    ws = Workspace(
        id=ws_id,
        name=workspace_name,
        app_id='boring-ui',
        created_by='owner-uuid',
    )
    await ws_repo.create(ws)
    member = Member(
        id=0,
        workspace_id=ws_id,
        user_id=None,
        email=email,
        role='admin',
        status='pending',
        invited_by='owner-uuid',
    )
    await member_repo.create(member)
    return ws_id


def _create_test_app():
    ws_repo = InMemoryWorkspaceRepository()
    member_repo = InMemoryMemberRepository()
    app = FastAPI()
    verifier = TokenVerifier(
        key_provider=StaticKeyProvider(TEST_SECRET),
        audience=TEST_AUDIENCE,
        algorithms=['HS256'],
    )
    app.add_middleware(
        AuthGuardMiddleware,
        token_verifier=verifier,
        require_auth=True,
    )
    ws_router = create_workspace_router(
        ws_repo, member_repo=member_repo,
    )
    app.include_router(ws_router)
    return app, ws_repo, member_repo


@pytest.fixture
def setup():
    return _create_test_app()


@pytest.fixture
def app(setup):
    return setup[0]


@pytest.fixture
def ws_repo(setup):
    return setup[1]


@pytest.fixture
def member_repo(setup):
    return setup[2]


# =====================================================================
# 1. Auto-accept on workspace list
# =====================================================================


class TestAutoAcceptOnList:

    @pytest.mark.asyncio
    async def test_pending_invite_auto_accepted_on_list(
        self, app, ws_repo, member_repo,
    ):
        await _setup_workspace_with_invite(ws_repo, member_repo)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            ws = r.json()['workspaces']
            assert len(ws) == 1
            assert ws[0]['workspace_id'] == 'ws_invited'
            assert ws[0]['name'] == 'Invited WS'

    @pytest.mark.asyncio
    async def test_invite_status_changed_to_active(
        self, app, ws_repo, member_repo,
    ):
        await _setup_workspace_with_invite(ws_repo, member_repo)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )

        # Verify the member record was updated
        members = await member_repo.list_for_workspace('ws_invited')
        assert len(members) == 1
        assert members[0].status == 'active'
        assert members[0].user_id == 'invitee-uuid'

    @pytest.mark.asyncio
    async def test_case_insensitive_email_match(
        self, app, ws_repo, member_repo,
    ):
        """Invite for INVITEE@EXAMPLE.COM should match invitee@example.com."""
        await _setup_workspace_with_invite(
            ws_repo, member_repo,
            email='INVITEE@EXAMPLE.COM',
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(email='invitee@example.com'),
            )
            assert r.status_code == 200
            assert len(r.json()['workspaces']) == 1

    @pytest.mark.asyncio
    async def test_no_match_different_email(
        self, app, ws_repo, member_repo,
    ):
        """Invite for other@example.com should not match invitee."""
        await _setup_workspace_with_invite(
            ws_repo, member_repo,
            email='other@example.com',
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            assert r.json()['workspaces'] == []

    @pytest.mark.asyncio
    async def test_already_active_idempotent(
        self, app, ws_repo, member_repo,
    ):
        """Calling list twice doesn't cause errors."""
        await _setup_workspace_with_invite(ws_repo, member_repo)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r1 = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )
            assert r1.status_code == 200
            assert len(r1.json()['workspaces']) == 1

            r2 = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )
            assert r2.status_code == 200
            assert len(r2.json()['workspaces']) == 1

    @pytest.mark.asyncio
    async def test_removed_invite_not_auto_accepted(
        self, app, ws_repo, member_repo,
    ):
        """Removed invites should not be auto-accepted."""
        await _setup_workspace_with_invite(ws_repo, member_repo)

        # Manually set the member to removed
        for m in member_repo._members.values():
            if m.workspace_id == 'ws_invited':
                m.status = 'removed'

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            assert r.json()['workspaces'] == []

    @pytest.mark.asyncio
    async def test_multiple_invites_all_accepted(
        self, app, ws_repo, member_repo,
    ):
        """Multiple pending invites for the same email all get accepted."""
        await _setup_workspace_with_invite(
            ws_repo, member_repo,
            workspace_name='WS A', ws_id='ws_a',
        )
        await _setup_workspace_with_invite(
            ws_repo, member_repo,
            workspace_name='WS B', ws_id='ws_b',
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            ws = r.json()['workspaces']
            assert len(ws) == 2
            ids = {w['workspace_id'] for w in ws}
            assert ids == {'ws_a', 'ws_b'}

    @pytest.mark.asyncio
    async def test_without_member_repo_no_auto_accept(self):
        """When member_repo is not provided, no auto-accept happens."""
        ws_repo = InMemoryWorkspaceRepository()
        app = FastAPI()
        verifier = TokenVerifier(
            key_provider=StaticKeyProvider(TEST_SECRET),
            audience=TEST_AUDIENCE,
            algorithms=['HS256'],
        )
        app.add_middleware(
            AuthGuardMiddleware,
            token_verifier=verifier,
            require_auth=True,
        )
        ws_router = create_workspace_router(ws_repo)  # No member_repo
        app.include_router(ws_router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            assert r.json()['workspaces'] == []
