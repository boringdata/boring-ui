"""Cross-cutting integration tests for workspace lifecycle, membership, and invites.

Bead: bd-1rtl (C5)

Exercises the full workspace lifecycle end-to-end across CRUD, membership,
and invite subsystems:
  - Full lifecycle: create workspace → invite → auto-accept → list members → remove → reinvite
  - Cross-tenant isolation: user A cannot see/access user B workspaces
  - Invite-to-membership round-trip with auto-accept on login
  - Soft-removal lifecycle: pending → active → removed → reinvite → active
  - App-scoped workspace isolation: same name OK in different apps
  - Multi-workspace user: member of several workspaces via invites
  - Error path: duplicate invite, double remove, reinvite after remove
  - Email normalization across invite and auto-accept
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
    create_member_router,
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


# ── Shared constants ─────────────────────────────────────────────────

TEST_SECRET = 'test-lifecycle-secret'
TEST_AUDIENCE = 'authenticated'


def _make_token(
    user_id: str = 'user-1',
    email: str = 'user1@example.com',
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


def _auth(user_id: str = 'user-1', email: str = 'user1@example.com') -> dict:
    return {'Authorization': f'Bearer {_make_token(user_id=user_id, email=email)}'}


def _build_app():
    """Build app with workspace + member routers wired together."""
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
    # Workspace router with member_repo for auto-accept.
    ws_router = create_workspace_router(ws_repo, member_repo=member_repo)
    app.include_router(ws_router)
    # Member router.
    member_router = create_member_router(member_repo)
    app.include_router(member_router)
    return app, ws_repo, member_repo


@pytest.fixture
def setup():
    return _build_app()


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
# 1. Full lifecycle: create → invite → accept → list → remove → reinvite
# =====================================================================


class TestFullLifecycle:
    """End-to-end lifecycle from workspace creation through member management."""

    @pytest.mark.asyncio
    async def test_create_invite_accept_remove_reinvite(self, app, member_repo):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # Step 1: Owner creates workspace.
            r = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Lifecycle WS'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.status_code == 202
            ws_id = r.json()['workspace_id']

            # Step 2: Owner invites a colleague.
            r = await c.post(
                f'/api/v1/workspaces/{ws_id}/members',
                json={'email': 'colleague@example.com'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.status_code == 201
            assert r.json()['status'] == 'pending'
            member_id = r.json()['member_id']

            # Step 3: Colleague loads workspaces → auto-accept.
            r = await c.get(
                '/api/v1/workspaces',
                headers=_auth(user_id='colleague', email='colleague@example.com'),
            )
            assert r.status_code == 200
            ws = r.json()['workspaces']
            assert len(ws) == 1
            assert ws[0]['workspace_id'] == ws_id

            # Verify member status changed to active.
            r = await c.get(
                f'/api/v1/workspaces/{ws_id}/members',
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            members = r.json()['members']
            colleague_member = next(
                m for m in members if m['email'] == 'colleague@example.com'
            )
            assert colleague_member['status'] == 'active'
            assert colleague_member['user_id'] == 'colleague'

            # Step 4: Owner removes colleague.
            r = await c.delete(
                f'/api/v1/workspaces/{ws_id}/members/{member_id}',
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.status_code == 200
            assert r.json()['status'] == 'removed'

            # Verify removed member excluded from default list.
            r = await c.get(
                f'/api/v1/workspaces/{ws_id}/members',
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.json()['members'] == []

            # Step 5: Owner re-invites colleague (allowed after removal).
            r = await c.post(
                f'/api/v1/workspaces/{ws_id}/members',
                json={'email': 'colleague@example.com'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.status_code == 201
            assert r.json()['status'] == 'pending'


# =====================================================================
# 2. Cross-tenant workspace isolation
# =====================================================================


class TestCrossTenantIsolation:
    """Users can only see their own workspaces."""

    @pytest.mark.asyncio
    async def test_user_a_cannot_see_user_b_workspaces(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # User A creates a workspace.
            await c.post(
                '/api/v1/workspaces',
                json={'name': 'User A Private'},
                headers=_auth(user_id='user-a', email='a@example.com'),
            )

            # User B sees nothing.
            r = await c.get(
                '/api/v1/workspaces',
                headers=_auth(user_id='user-b', email='b@example.com'),
            )
            assert r.status_code == 200
            assert r.json()['workspaces'] == []

    @pytest.mark.asyncio
    async def test_each_user_sees_only_own(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await c.post(
                '/api/v1/workspaces',
                json={'name': 'WS Alpha'},
                headers=_auth(user_id='alice', email='alice@example.com'),
            )
            await c.post(
                '/api/v1/workspaces',
                json={'name': 'WS Beta'},
                headers=_auth(user_id='bob', email='bob@example.com'),
            )

            # Alice sees only Alpha.
            r = await c.get(
                '/api/v1/workspaces',
                headers=_auth(user_id='alice', email='alice@example.com'),
            )
            names = [w['name'] for w in r.json()['workspaces']]
            assert names == ['WS Alpha']

            # Bob sees only Beta.
            r = await c.get(
                '/api/v1/workspaces',
                headers=_auth(user_id='bob', email='bob@example.com'),
            )
            names = [w['name'] for w in r.json()['workspaces']]
            assert names == ['WS Beta']

    @pytest.mark.asyncio
    async def test_invite_grants_cross_tenant_access(self, app):
        """After invite + accept, user B can see user A's workspace."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # User A creates workspace.
            r = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Shared WS'},
                headers=_auth(user_id='user-a', email='a@example.com'),
            )
            ws_id = r.json()['workspace_id']

            # User A invites User B.
            await c.post(
                f'/api/v1/workspaces/{ws_id}/members',
                json={'email': 'b@example.com'},
                headers=_auth(user_id='user-a', email='a@example.com'),
            )

            # User B loads workspaces → auto-accept → sees Shared WS.
            r = await c.get(
                '/api/v1/workspaces',
                headers=_auth(user_id='user-b', email='b@example.com'),
            )
            ws = r.json()['workspaces']
            assert len(ws) == 1
            assert ws[0]['name'] == 'Shared WS'


# =====================================================================
# 3. Multi-workspace member via invites
# =====================================================================


class TestMultiWorkspaceMember:
    """User gains membership in multiple workspaces through invites."""

    @pytest.mark.asyncio
    async def test_member_of_multiple_workspaces(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # Three different owners create workspaces.
            ws_ids = []
            for i in range(3):
                r = await c.post(
                    '/api/v1/workspaces',
                    json={'name': f'Team {i}'},
                    headers=_auth(
                        user_id=f'owner-{i}',
                        email=f'owner{i}@example.com',
                    ),
                )
                ws_ids.append(r.json()['workspace_id'])

            # Each owner invites the same user.
            for i, ws_id in enumerate(ws_ids):
                await c.post(
                    f'/api/v1/workspaces/{ws_id}/members',
                    json={'email': 'multi@example.com'},
                    headers=_auth(
                        user_id=f'owner-{i}',
                        email=f'owner{i}@example.com',
                    ),
                )

            # User loads workspaces → all 3 auto-accepted.
            r = await c.get(
                '/api/v1/workspaces',
                headers=_auth(user_id='multi-user', email='multi@example.com'),
            )
            assert len(r.json()['workspaces']) == 3
            returned_ids = {w['workspace_id'] for w in r.json()['workspaces']}
            assert returned_ids == set(ws_ids)


# =====================================================================
# 4. Soft-removal lifecycle transitions
# =====================================================================


class TestSoftRemovalLifecycle:
    """Validate status transitions: pending → active → removed → reinvite."""

    @pytest.mark.asyncio
    async def test_full_status_transitions(self, app, member_repo):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # Owner creates workspace.
            r = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Status WS'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            ws_id = r.json()['workspace_id']

            # Invite → pending.
            r = await c.post(
                f'/api/v1/workspaces/{ws_id}/members',
                json={'email': 'target@example.com'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.json()['status'] == 'pending'
            mid = r.json()['member_id']

            # Auto-accept → active.
            await c.get(
                '/api/v1/workspaces',
                headers=_auth(user_id='target', email='target@example.com'),
            )
            member = await member_repo.get(mid)
            assert member.status == 'active'

            # Remove → removed.
            r = await c.delete(
                f'/api/v1/workspaces/{ws_id}/members/{mid}',
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.json()['status'] == 'removed'

            # Double remove → 409.
            r = await c.delete(
                f'/api/v1/workspaces/{ws_id}/members/{mid}',
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.status_code == 409
            assert r.json()['error'] == 'already_removed'

            # Reinvite → new pending.
            r = await c.post(
                f'/api/v1/workspaces/{ws_id}/members',
                json={'email': 'target@example.com'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.status_code == 201
            assert r.json()['status'] == 'pending'

    @pytest.mark.asyncio
    async def test_removed_member_not_in_default_list(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Remove Test'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            ws_id = r.json()['workspace_id']

            r = await c.post(
                f'/api/v1/workspaces/{ws_id}/members',
                json={'email': 'gone@example.com'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            mid = r.json()['member_id']

            await c.delete(
                f'/api/v1/workspaces/{ws_id}/members/{mid}',
                headers=_auth(user_id='owner', email='owner@example.com'),
            )

            # Default list excludes removed.
            r = await c.get(
                f'/api/v1/workspaces/{ws_id}/members',
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.json()['members'] == []

            # include_removed=true shows them.
            r = await c.get(
                f'/api/v1/workspaces/{ws_id}/members?include_removed=true',
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            members = r.json()['members']
            assert len(members) == 1
            assert members[0]['status'] == 'removed'


# =====================================================================
# 5. App-scoped workspace isolation
# =====================================================================


class TestAppScopedIsolation:
    """Workspaces in different apps are isolated."""

    @pytest.mark.asyncio
    async def test_same_name_different_app_allowed(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r1 = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Shared Name', 'app_id': 'app-alpha'},
                headers=_auth(user_id='u1', email='u1@example.com'),
            )
            assert r1.status_code == 202

            r2 = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Shared Name', 'app_id': 'app-beta'},
                headers=_auth(user_id='u1', email='u1@example.com'),
            )
            assert r2.status_code == 202

    @pytest.mark.asyncio
    async def test_list_filtered_by_app_id(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await c.post(
                '/api/v1/workspaces',
                json={'name': 'Alpha WS', 'app_id': 'app-alpha'},
                headers=_auth(user_id='u1', email='u1@example.com'),
            )
            await c.post(
                '/api/v1/workspaces',
                json={'name': 'Beta WS', 'app_id': 'app-beta'},
                headers=_auth(user_id='u1', email='u1@example.com'),
            )

            r = await c.get(
                '/api/v1/workspaces?app_id=app-alpha',
                headers=_auth(user_id='u1', email='u1@example.com'),
            )
            ws = r.json()['workspaces']
            assert len(ws) == 1
            assert ws[0]['name'] == 'Alpha WS'


# =====================================================================
# 6. Email normalization across invite + auto-accept
# =====================================================================


class TestEmailNormalization:
    """Email casing handled consistently across invite and accept flows."""

    @pytest.mark.asyncio
    async def test_mixed_case_invite_accepted_by_lowercase_login(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Case WS'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            ws_id = r.json()['workspace_id']

            # Invite with mixed case.
            await c.post(
                f'/api/v1/workspaces/{ws_id}/members',
                json={'email': '  Alice@EXAMPLE.COM  '},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )

            # Login with lowercase → auto-accept works.
            r = await c.get(
                '/api/v1/workspaces',
                headers=_auth(user_id='alice', email='alice@example.com'),
            )
            assert len(r.json()['workspaces']) == 1

    @pytest.mark.asyncio
    async def test_duplicate_detection_case_insensitive(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Dupe WS'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            ws_id = r.json()['workspace_id']

            r = await c.post(
                f'/api/v1/workspaces/{ws_id}/members',
                json={'email': 'bob@example.com'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.status_code == 201

            r = await c.post(
                f'/api/v1/workspaces/{ws_id}/members',
                json={'email': 'BOB@EXAMPLE.COM'},
                headers=_auth(user_id='owner', email='owner@example.com'),
            )
            assert r.status_code == 409
            assert r.json()['error'] == 'duplicate_invite'


# =====================================================================
# 7. Error paths
# =====================================================================


class TestErrorPaths:
    """Verify error codes on invalid operations."""

    @pytest.mark.asyncio
    async def test_duplicate_workspace_name_same_app(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await c.post(
                '/api/v1/workspaces',
                json={'name': 'Taken'},
                headers=_auth(user_id='u1', email='u1@example.com'),
            )
            r = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Taken'},
                headers=_auth(user_id='u1', email='u1@example.com'),
            )
            assert r.status_code == 409
            assert r.json()['error'] == 'workspace_exists'

    @pytest.mark.asyncio
    async def test_get_nonexistent_workspace(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get(
                '/api/v1/workspaces/ws_fake',
                headers=_auth(),
            )
            assert r.status_code == 404
            assert r.json()['error'] == 'workspace_not_found'

    @pytest.mark.asyncio
    async def test_remove_nonexistent_member(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.delete(
                '/api/v1/workspaces/ws_any/members/99999',
                headers=_auth(),
            )
            assert r.status_code == 404
            assert r.json()['error'] == 'member_not_found'

    @pytest.mark.asyncio
    async def test_invalid_email_invite(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/api/v1/workspaces/ws_any/members',
                json={'email': 'not-an-email'},
                headers=_auth(),
            )
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_all_endpoints_require_auth(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            for method, url in [
                ('GET', '/api/v1/workspaces'),
                ('POST', '/api/v1/workspaces'),
                ('GET', '/api/v1/workspaces/ws_1'),
                ('PATCH', '/api/v1/workspaces/ws_1'),
                ('POST', '/api/v1/workspaces/ws_1/members'),
                ('GET', '/api/v1/workspaces/ws_1/members'),
                ('DELETE', '/api/v1/workspaces/ws_1/members/1'),
            ]:
                r = await c.request(method, url)
                assert r.status_code == 401, f'{method} {url} should require auth'


# =====================================================================
# 8. Workspace CRUD round-trip
# =====================================================================


class TestWorkspaceCRUDRoundTrip:
    """Create → get → patch → get verifies persistence."""

    @pytest.mark.asyncio
    async def test_create_get_patch_get(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            # Create.
            r = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Original Name'},
                headers=_auth(),
            )
            assert r.status_code == 202
            ws_id = r.json()['workspace_id']

            # Get.
            r = await c.get(
                f'/api/v1/workspaces/{ws_id}',
                headers=_auth(),
            )
            assert r.json()['name'] == 'Original Name'

            # Patch.
            r = await c.patch(
                f'/api/v1/workspaces/{ws_id}',
                json={'name': 'Renamed'},
                headers=_auth(),
            )
            assert r.status_code == 200
            assert r.json()['name'] == 'Renamed'

            # Get again.
            r = await c.get(
                f'/api/v1/workspaces/{ws_id}',
                headers=_auth(),
            )
            assert r.json()['name'] == 'Renamed'

    @pytest.mark.asyncio
    async def test_rename_collision_blocked(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await c.post(
                '/api/v1/workspaces',
                json={'name': 'Existing'},
                headers=_auth(),
            )
            r = await c.post(
                '/api/v1/workspaces',
                json={'name': 'Temp'},
                headers=_auth(),
            )
            ws_id = r.json()['workspace_id']

            r = await c.patch(
                f'/api/v1/workspaces/{ws_id}',
                json={'name': 'Existing'},
                headers=_auth(),
            )
            assert r.status_code == 409
