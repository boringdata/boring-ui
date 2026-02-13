"""Tests for workspace CRUD endpoints.

Bead: bd-223o.9.1 (C1)

Validates:
  - POST /api/v1/workspaces creates workspace and returns 202
  - GET /api/v1/workspaces lists user's workspaces
  - GET /api/v1/workspaces/{id} returns workspace details
  - PATCH /api/v1/workspaces/{id} updates workspace name
  - Duplicate workspace name returns 409
  - Missing workspace returns 404
  - All endpoints require authentication (401 without token)
  - Empty/invalid requests return 400/422
"""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from control_plane.app.routes.workspaces import (
    InMemoryWorkspaceRepository,
    create_workspace_router,
)
from control_plane.app.security.auth_guard import AuthGuardMiddleware
from control_plane.app.security.token_verify import (
    StaticKeyProvider,
    TokenVerifier,
)

# ── Test constants ────────────────────────────────────────────────────

TEST_SECRET = 'test-workspace-secret'
TEST_AUDIENCE = 'authenticated'


def _make_token(
    user_id: str = 'user-uuid-ws',
    email: str = 'ws@example.com',
    **overrides,
) -> str:
    payload = {
        'sub': user_id,
        'email': email,
        'role': 'authenticated',
        'aud': TEST_AUDIENCE,
        'exp': int(time.time()) + 3600,
        'iat': int(time.time()),
    }
    payload.update(overrides)
    return jwt.encode(payload, TEST_SECRET, algorithm='HS256')


def _create_verifier() -> TokenVerifier:
    return TokenVerifier(
        key_provider=StaticKeyProvider(TEST_SECRET),
        audience=TEST_AUDIENCE,
        algorithms=['HS256'],
    )


def _create_test_app(repo=None) -> tuple[FastAPI, InMemoryWorkspaceRepository]:
    if repo is None:
        repo = InMemoryWorkspaceRepository()
    app = FastAPI()
    app.add_middleware(
        AuthGuardMiddleware,
        token_verifier=_create_verifier(),
        require_auth=True,
    )
    ws_router = create_workspace_router(repo)
    app.include_router(ws_router)
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


def _auth_headers(user_id: str = 'user-uuid-ws') -> dict:
    return {'Authorization': f'Bearer {_make_token(user_id=user_id)}'}


# =====================================================================
# 1. Create workspace
# =====================================================================


class TestCreateWorkspace:

    @pytest.mark.asyncio
    async def test_create_returns_202(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                '/api/v1/workspaces',
                json={'name': 'My Workspace'},
                headers=_auth_headers(),
            )
            assert r.status_code == 202
            data = r.json()
            assert data['name'] == 'My Workspace'
            assert data['app_id'] == 'boring-ui'
            assert data['workspace_id'].startswith('ws_')
            assert data['created_by'] == 'user-uuid-ws'

    @pytest.mark.asyncio
    async def test_create_with_custom_app_id(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Custom App', 'app_id': 'custom-app'},
                headers=_auth_headers(),
            )
            assert r.status_code == 202
            assert r.json()['app_id'] == 'custom-app'

    @pytest.mark.asyncio
    async def test_create_duplicate_name_returns_409(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r1 = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Dupe Name'},
                headers=_auth_headers(),
            )
            assert r1.status_code == 202

            r2 = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Dupe Name'},
                headers=_auth_headers(),
            )
            assert r2.status_code == 409
            assert r2.json()['error'] == 'workspace_exists'

    @pytest.mark.asyncio
    async def test_create_requires_auth(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Unauthorized'},
            )
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_create_empty_name_returns_422(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                '/api/v1/workspaces',
                json={'name': ''},
                headers=_auth_headers(),
            )
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_create_missing_name_returns_422(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.post(
                '/api/v1/workspaces',
                json={},
                headers=_auth_headers(),
            )
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_same_name_different_app_id_ok(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r1 = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Shared Name', 'app_id': 'app-a'},
                headers=_auth_headers(),
            )
            assert r1.status_code == 202

            r2 = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Shared Name', 'app_id': 'app-b'},
                headers=_auth_headers(),
            )
            assert r2.status_code == 202


# =====================================================================
# 2. List workspaces
# =====================================================================


class TestListWorkspaces:

    @pytest.mark.asyncio
    async def test_list_empty(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            assert r.json()['workspaces'] == []

    @pytest.mark.asyncio
    async def test_list_returns_user_workspaces(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            await client.post(
                '/api/v1/workspaces',
                json={'name': 'WS One'},
                headers=_auth_headers(),
            )
            await client.post(
                '/api/v1/workspaces',
                json={'name': 'WS Two'},
                headers=_auth_headers(),
            )

            r = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            ws = r.json()['workspaces']
            assert len(ws) == 2
            names = [w['name'] for w in ws]
            assert 'WS One' in names
            assert 'WS Two' in names

    @pytest.mark.asyncio
    async def test_list_filters_by_user(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            # User A creates a workspace
            await client.post(
                '/api/v1/workspaces',
                json={'name': 'User A WS'},
                headers=_auth_headers(user_id='user-a'),
            )

            # User B should not see it
            r = await client.get(
                '/api/v1/workspaces',
                headers=_auth_headers(user_id='user-b'),
            )
            assert r.status_code == 200
            assert r.json()['workspaces'] == []

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/workspaces')
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_list_filters_by_app_id(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            await client.post(
                '/api/v1/workspaces',
                json={'name': 'App A', 'app_id': 'app-a'},
                headers=_auth_headers(),
            )
            await client.post(
                '/api/v1/workspaces',
                json={'name': 'App B', 'app_id': 'app-b'},
                headers=_auth_headers(),
            )

            r = await client.get(
                '/api/v1/workspaces?app_id=app-a',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            ws = r.json()['workspaces']
            assert len(ws) == 1
            assert ws[0]['name'] == 'App A'


# =====================================================================
# 3. Get workspace
# =====================================================================


class TestGetWorkspace:

    @pytest.mark.asyncio
    async def test_get_existing_workspace(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            create_r = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Get Me'},
                headers=_auth_headers(),
            )
            ws_id = create_r.json()['workspace_id']

            r = await client.get(
                f'/api/v1/workspaces/{ws_id}',
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            data = r.json()
            assert data['workspace_id'] == ws_id
            assert data['name'] == 'Get Me'
            assert 'created_at' in data
            assert 'updated_at' in data

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get(
                '/api/v1/workspaces/ws_nonexistent',
                headers=_auth_headers(),
            )
            assert r.status_code == 404
            assert r.json()['error'] == 'workspace_not_found'

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.get('/api/v1/workspaces/ws_123')
            assert r.status_code == 401


# =====================================================================
# 4. Patch workspace
# =====================================================================


class TestPatchWorkspace:

    @pytest.mark.asyncio
    async def test_patch_name(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            create_r = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Old Name'},
                headers=_auth_headers(),
            )
            ws_id = create_r.json()['workspace_id']

            r = await client.patch(
                f'/api/v1/workspaces/{ws_id}',
                json={'name': 'New Name'},
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            assert r.json()['name'] == 'New Name'

    @pytest.mark.asyncio
    async def test_patch_nonexistent_returns_404(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.patch(
                '/api/v1/workspaces/ws_nonexistent',
                json={'name': 'New Name'},
                headers=_auth_headers(),
            )
            assert r.status_code == 404
            assert r.json()['error'] == 'workspace_not_found'

    @pytest.mark.asyncio
    async def test_patch_duplicate_name_returns_409(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            await client.post(
                '/api/v1/workspaces',
                json={'name': 'Taken Name'},
                headers=_auth_headers(),
            )
            create_r = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Other Name'},
                headers=_auth_headers(),
            )
            ws_id = create_r.json()['workspace_id']

            r = await client.patch(
                f'/api/v1/workspaces/{ws_id}',
                json={'name': 'Taken Name'},
                headers=_auth_headers(),
            )
            assert r.status_code == 409
            assert r.json()['error'] == 'workspace_exists'

    @pytest.mark.asyncio
    async def test_patch_same_name_ok(self, app):
        """Patching with the current name should succeed (no-op rename)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            create_r = await client.post(
                '/api/v1/workspaces',
                json={'name': 'Same Name'},
                headers=_auth_headers(),
            )
            ws_id = create_r.json()['workspace_id']

            r = await client.patch(
                f'/api/v1/workspaces/{ws_id}',
                json={'name': 'Same Name'},
                headers=_auth_headers(),
            )
            assert r.status_code == 200
            assert r.json()['name'] == 'Same Name'

    @pytest.mark.asyncio
    async def test_patch_no_fields_returns_400(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            create_r = await client.post(
                '/api/v1/workspaces',
                json={'name': 'No Update'},
                headers=_auth_headers(),
            )
            ws_id = create_r.json()['workspace_id']

            r = await client.patch(
                f'/api/v1/workspaces/{ws_id}',
                json={},
                headers=_auth_headers(),
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'invalid_request'

    @pytest.mark.asyncio
    async def test_patch_requires_auth(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            r = await client.patch(
                '/api/v1/workspaces/ws_123',
                json={'name': 'New Name'},
            )
            assert r.status_code == 401


# =====================================================================
# 5. InMemoryWorkspaceRepository unit tests
# =====================================================================


class TestInMemoryRepository:

    @pytest.mark.asyncio
    async def test_create_and_get(self):
        from control_plane.app.routes.workspaces import Workspace
        repo = InMemoryWorkspaceRepository()
        ws = Workspace(
            id='ws_test', name='Test', app_id='app',
            created_by='user-1',
        )
        await repo.create(ws)
        result = await repo.get('ws_test')
        assert result is not None
        assert result.name == 'Test'

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        repo = InMemoryWorkspaceRepository()
        assert await repo.get('ws_missing') is None

    @pytest.mark.asyncio
    async def test_list_filters_by_membership(self):
        from control_plane.app.routes.workspaces import Workspace
        repo = InMemoryWorkspaceRepository()
        ws1 = Workspace(
            id='ws_1', name='WS1', app_id='app', created_by='user-a',
        )
        ws2 = Workspace(
            id='ws_2', name='WS2', app_id='app', created_by='user-b',
        )
        await repo.create(ws1)
        await repo.create(ws2)

        result = await repo.list_for_user('user-a', 'app')
        assert len(result) == 1
        assert result[0].id == 'ws_1'

    @pytest.mark.asyncio
    async def test_exists_name(self):
        from control_plane.app.routes.workspaces import Workspace
        repo = InMemoryWorkspaceRepository()
        ws = Workspace(
            id='ws_1', name='Exists', app_id='app', created_by='u',
        )
        await repo.create(ws)
        assert await repo.exists_name('Exists', 'app') is True
        assert await repo.exists_name('Nope', 'app') is False
        assert await repo.exists_name('Exists', 'other-app') is False

    @pytest.mark.asyncio
    async def test_update(self):
        from control_plane.app.routes.workspaces import Workspace
        repo = InMemoryWorkspaceRepository()
        ws = Workspace(
            id='ws_1', name='Old', app_id='app', created_by='u',
        )
        await repo.create(ws)
        updated = await repo.update('ws_1', name='New')
        assert updated.name == 'New'

    @pytest.mark.asyncio
    async def test_update_nonexistent(self):
        repo = InMemoryWorkspaceRepository()
        assert await repo.update('ws_missing', name='X') is None
