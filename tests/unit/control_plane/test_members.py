"""Tests for workspace membership and invite endpoints.

Bead: bd-223o.9.2 (C2)

Validates:
  - POST /api/v1/workspaces/{id}/members creates pending invite (201)
  - Duplicate pending invite returns 409
  - GET /api/v1/workspaces/{id}/members lists active/pending members
  - DELETE soft-removes member (status → removed)
  - Removed members excluded from default listing
  - include_removed=true shows all members
  - Double removal returns 409
  - All endpoints require authentication
  - Invalid email/role rejected (422)
  - Email normalized to lowercase
"""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from control_plane.app.routes.members import (
    InMemoryMemberRepository,
    create_member_router,
)
from control_plane.app.security.auth_guard import AuthGuardMiddleware
from control_plane.app.security.token_verify import (
    StaticKeyProvider,
    TokenVerifier,
)

# ── Test constants ────────────────────────────────────────────────────

TEST_SECRET = 'test-member-secret'
TEST_AUDIENCE = 'authenticated'
WS_ID = 'ws_test123'


def _make_token(
    user_id: str = 'user-uuid-m',
    email: str = 'member@example.com',
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


def _auth_headers(user_id: str = 'user-uuid-m') -> dict:
    return {'Authorization': f'Bearer {_make_token(user_id=user_id)}'}


def _create_test_app() -> tuple[FastAPI, InMemoryMemberRepository]:
    repo = InMemoryMemberRepository()
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
    member_router = create_member_router(repo)
    app.include_router(member_router)
    return app, repo


@pytest.fixture
def app_and_repo():
    return _create_test_app()


@pytest.fixture
def app(app_and_repo):
    return app_and_repo[0]


@pytest.fixture
def repo(app_and_repo):
    return app_and_repo[1]


# =====================================================================
# 1. Invite member (POST)
# =====================================================================


class TestInviteMember:

    @pytest.mark.asyncio
    async def test_invite_creates_pending_member(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'invited@example.com'},
                headers=_auth_headers(),
            )
            assert r.status_code == 201
            data = r.json()
            assert data['email'] == 'invited@example.com'
            assert data['role'] == 'admin'
            assert data['status'] == 'pending'
            assert data['workspace_id'] == WS_ID
            assert 'member_id' in data

    @pytest.mark.asyncio
    async def test_duplicate_invite_returns_409(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r1 = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'dupe@example.com'},
                headers=_auth_headers(),
            )
            assert r1.status_code == 201

            r2 = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'dupe@example.com'},
                headers=_auth_headers(),
            )
            assert r2.status_code == 409
            assert r2.json()['error'] == 'duplicate_invite'

    @pytest.mark.asyncio
    async def test_duplicate_case_insensitive(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r1 = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'Test@Example.COM'},
                headers=_auth_headers(),
            )
            assert r1.status_code == 201

            r2 = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'test@example.com'},
                headers=_auth_headers(),
            )
            assert r2.status_code == 409

    @pytest.mark.asyncio
    async def test_email_normalized(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': '  User@EXAMPLE.com  '},
                headers=_auth_headers(),
            )
            assert r.status_code == 201
            assert r.json()['email'] == 'user@example.com'

    @pytest.mark.asyncio
    async def test_invalid_email_returns_422(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'not-an-email'},
                headers=_auth_headers(),
            )
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_role_returns_422(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'ok@example.com', 'role': 'viewer'},
                headers=_auth_headers(),
            )
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_invite_requires_auth(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'noauth@example.com'},
            )
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_different_workspace_same_email_ok(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r1 = await client.post(
                '/api/v1/workspaces/ws_a/members',
                json={'email': 'shared@example.com'},
                headers=_auth_headers(),
            )
            assert r1.status_code == 201

            r2 = await client.post(
                '/api/v1/workspaces/ws_b/members',
                json={'email': 'shared@example.com'},
                headers=_auth_headers(),
            )
            assert r2.status_code == 201


# =====================================================================
# 2. List members (GET)
# =====================================================================


class TestListMembers:

    @pytest.mark.asyncio
    async def test_list_empty_workspace(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                f'/api/v1/workspaces/{WS_ID}/members',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            assert r.json()['members'] == []

    @pytest.mark.asyncio
    async def test_list_returns_invited_members(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'a@example.com'},
                headers=_auth_headers(),
            )
            await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'b@example.com'},
                headers=_auth_headers(),
            )

            r = await client.get(
                f'/api/v1/workspaces/{WS_ID}/members',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            members = r.json()['members']
            assert len(members) == 2
            emails = [m['email'] for m in members]
            assert 'a@example.com' in emails
            assert 'b@example.com' in emails

    @pytest.mark.asyncio
    async def test_list_excludes_removed_by_default(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            create_r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'removed@example.com'},
                headers=_auth_headers(),
            )
            member_id = create_r.json()['member_id']

            await client.delete(
                f'/api/v1/workspaces/{WS_ID}/members/{member_id}',
                headers=_auth_headers(),
            )

            r = await client.get(
                f'/api/v1/workspaces/{WS_ID}/members',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            assert r.json()['members'] == []

    @pytest.mark.asyncio
    async def test_list_includes_removed_when_requested(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            create_r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'removed@example.com'},
                headers=_auth_headers(),
            )
            member_id = create_r.json()['member_id']

            await client.delete(
                f'/api/v1/workspaces/{WS_ID}/members/{member_id}',
                headers=_auth_headers(),
            )

            r = await client.get(
                f'/api/v1/workspaces/{WS_ID}/members?include_removed=true',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            members = r.json()['members']
            assert len(members) == 1
            assert members[0]['status'] == 'removed'

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(f'/api/v1/workspaces/{WS_ID}/members')
            assert r.status_code == 401


# =====================================================================
# 3. Remove member (DELETE)
# =====================================================================


class TestRemoveMember:

    @pytest.mark.asyncio
    async def test_remove_sets_status_removed(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            create_r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'target@example.com'},
                headers=_auth_headers(),
            )
            member_id = create_r.json()['member_id']

            r = await client.delete(
                f'/api/v1/workspaces/{WS_ID}/members/{member_id}',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            assert r.json()['status'] == 'removed'
            assert r.json()['email'] == 'target@example.com'

    @pytest.mark.asyncio
    async def test_remove_nonexistent_returns_404(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.delete(
                f'/api/v1/workspaces/{WS_ID}/members/99999',
                headers=_auth_headers(),
            )
            assert r.status_code == 404
            assert r.json()['error'] == 'member_not_found'

    @pytest.mark.asyncio
    async def test_double_remove_returns_409(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            create_r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'twice@example.com'},
                headers=_auth_headers(),
            )
            member_id = create_r.json()['member_id']

            r1 = await client.delete(
                f'/api/v1/workspaces/{WS_ID}/members/{member_id}',
                headers=_auth_headers(),
            )
            assert r1.status_code == 200

            r2 = await client.delete(
                f'/api/v1/workspaces/{WS_ID}/members/{member_id}',
                headers=_auth_headers(),
            )
            assert r2.status_code == 409
            assert r2.json()['error'] == 'already_removed'

    @pytest.mark.asyncio
    async def test_remove_wrong_workspace_returns_404(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            create_r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'cross@example.com'},
                headers=_auth_headers(),
            )
            member_id = create_r.json()['member_id']

            # Try to remove from a different workspace
            r = await client.delete(
                f'/api/v1/workspaces/ws_other/members/{member_id}',
                headers=_auth_headers(),
            )
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_requires_auth(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.delete(
                f'/api/v1/workspaces/{WS_ID}/members/1',
            )
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_reinvite_after_removal_allowed(self, app):
        """After removal, the same email can be re-invited."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # Invite
            create_r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'reinvite@example.com'},
                headers=_auth_headers(),
            )
            member_id = create_r.json()['member_id']

            # Remove
            await client.delete(
                f'/api/v1/workspaces/{WS_ID}/members/{member_id}',
                headers=_auth_headers(),
            )

            # Re-invite should succeed
            r = await client.post(
                f'/api/v1/workspaces/{WS_ID}/members',
                json={'email': 'reinvite@example.com'},
                headers=_auth_headers(),
            )
            assert r.status_code == 201
            assert r.json()['status'] == 'pending'
