"""Tests for share-link create/revoke/list API endpoints.

Bead: bd-223o.12.2 (F2)

Validates:
  - Share creation with membership gate and path normalization.
  - Non-member access denied with 403.
  - Token returned once in create response (plaintext not stored).
  - Share listing per workspace with revoked filter.
  - Idempotent revoke behavior.
  - Path traversal rejected with 400.
  - Invalid access mode rejected with 400.
  - Expiry bounds enforced.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from control_plane.app.agent.sessions import (
    InMemoryMembershipChecker,
)
from control_plane.app.sharing.model import (
    InMemoryShareLinkRepository,
    hash_token,
)
from control_plane.app.sharing.routes import (
    CreateShareRequest,
    create_share_router,
    normalize_share_path,
)
from control_plane.app.security.token_verify import AuthIdentity


# ── Test helpers ──────────────────────────────────────────────────────


def _make_app(
    members: set[tuple[str, str]] | None = None,
    user_id: str = 'user_1',
    email: str = 'user@test.com',
) -> FastAPI:
    """Build a test app with share routes and fake auth."""
    app = FastAPI()
    repo = InMemoryShareLinkRepository()
    checker = InMemoryMembershipChecker(members or set())

    router = create_share_router(repo, checker)
    app.include_router(router)

    @app.middleware('http')
    async def fake_auth(request: Request, call_next):
        request.state.auth_identity = AuthIdentity(
            user_id=user_id,
            email=email,
            role='authenticated',
        )
        return await call_next(request)

    app.state.share_repo = repo
    app.state.membership = checker

    return app


@pytest.fixture
def member_app():
    """App where user_1 is a member of ws_1."""
    return _make_app(members={('ws_1', 'user_1')})


@pytest.fixture
def no_member_app():
    """App where user_1 is NOT a member of any workspace."""
    return _make_app(members=set())


# =====================================================================
# Path normalization (unit tests)
# =====================================================================


class TestNormalizeSharePath:
    """normalize_share_path correctness."""

    def test_absolute_path_unchanged(self):
        assert normalize_share_path('/docs/README.md') == '/docs/README.md'

    def test_relative_path_rejected(self):
        assert normalize_share_path('docs/README.md') is None

    def test_empty_path_rejected(self):
        assert normalize_share_path('') is None

    def test_traversal_rejected(self):
        assert normalize_share_path('/docs/../../../etc/passwd') is None

    def test_double_slash_normalized(self):
        assert normalize_share_path('/docs//README.md') == '/docs/README.md'

    def test_dot_segment_normalized(self):
        assert normalize_share_path('/docs/./README.md') == '/docs/README.md'

    def test_root_path_valid(self):
        assert normalize_share_path('/') == '/'

    def test_trailing_slash_stripped(self):
        assert normalize_share_path('/docs/') == '/docs'


# =====================================================================
# Share creation
# =====================================================================


class TestCreateShare:
    """POST /w/{workspace_id}/api/v1/shares."""

    @pytest.mark.asyncio
    async def test_create_returns_201(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/docs/README.md'},
            )
            assert r.status_code == 201

    @pytest.mark.asyncio
    async def test_create_returns_plaintext_token(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/docs/README.md'},
            )
            data = r.json()
            assert 'token' in data
            assert len(data['token']) > 20  # URL-safe token.

    @pytest.mark.asyncio
    async def test_create_returns_share_metadata(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/docs/README.md', 'access': 'write'},
            )
            data = r.json()
            assert data['workspace_id'] == 'ws_1'
            assert data['path'] == '/docs/README.md'
            assert data['access'] == 'write'
            assert data['created_by'] == 'user_1'
            assert 'expires_at' in data
            assert 'share_id' in data

    @pytest.mark.asyncio
    async def test_token_hash_stored_not_plaintext(self, member_app):
        """Plaintext token is NOT stored; only hash is persisted."""
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/docs/README.md'},
            )
            data = r.json()
            plaintext = data['token']
            expected_hash = hash_token(plaintext)

            # Check repository directly.
            repo = member_app.state.share_repo
            link = await repo.get_by_token_hash(expected_hash)
            assert link is not None
            assert link.token_hash == expected_hash
            # Plaintext should not appear in any stored field.
            assert plaintext != link.token_hash

    @pytest.mark.asyncio
    async def test_create_default_access_is_read(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/file.txt'},
            )
            assert r.json()['access'] == 'read'

    @pytest.mark.asyncio
    async def test_non_member_gets_403(self, no_member_app):
        transport = ASGITransport(app=no_member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/file.txt'},
            )
            assert r.status_code == 403
            assert r.json()['error'] == 'forbidden'

    @pytest.mark.asyncio
    async def test_traversal_path_rejected(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/docs/../../../etc/passwd'},
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'invalid_path'

    @pytest.mark.asyncio
    async def test_relative_path_rejected(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': 'docs/file.txt'},
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'invalid_path'

    @pytest.mark.asyncio
    async def test_invalid_access_mode_rejected(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/file.txt', 'access': 'admin'},
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'invalid_access'

    @pytest.mark.asyncio
    async def test_custom_expiry_hours(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/file.txt', 'expires_in_hours': 1},
            )
            assert r.status_code == 201

    @pytest.mark.asyncio
    async def test_expiry_too_low_rejected(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/file.txt', 'expires_in_hours': 0},
            )
            assert r.status_code == 422  # Pydantic validation.

    @pytest.mark.asyncio
    async def test_expiry_too_high_rejected(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/file.txt', 'expires_in_hours': 800},
            )
            assert r.status_code == 422  # Pydantic validation.

    @pytest.mark.asyncio
    async def test_path_normalized_in_response(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/docs//README.md'},
            )
            assert r.json()['path'] == '/docs/README.md'

    @pytest.mark.asyncio
    async def test_unique_tokens_per_share(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r1 = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/file.txt'},
            )
            r2 = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': '/file.txt'},
            )
            assert r1.json()['token'] != r2.json()['token']


# =====================================================================
# Share listing
# =====================================================================


class TestListShares:
    """GET /w/{workspace_id}/api/v1/shares."""

    @pytest.mark.asyncio
    async def test_list_returns_created_shares(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await c.post('/w/ws_1/api/v1/shares', json={'path': '/a.txt'})
            await c.post('/w/ws_1/api/v1/shares', json={'path': '/b.txt'})
            r = await c.get('/w/ws_1/api/v1/shares')
            assert r.status_code == 200
            assert len(r.json()['shares']) == 2

    @pytest.mark.asyncio
    async def test_list_empty_workspace(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/w/ws_1/api/v1/shares')
            assert r.json()['shares'] == []

    @pytest.mark.asyncio
    async def test_list_non_member_gets_403(self, no_member_app):
        transport = ASGITransport(app=no_member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/w/ws_1/api/v1/shares')
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_list_excludes_revoked_by_default(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/shares', json={'path': '/a.txt'})
            sid = cr.json()['share_id']
            await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            r = await c.get('/w/ws_1/api/v1/shares')
            assert len(r.json()['shares']) == 0

    @pytest.mark.asyncio
    async def test_list_includes_revoked_when_requested(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/shares', json={'path': '/a.txt'})
            sid = cr.json()['share_id']
            await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            r = await c.get('/w/ws_1/api/v1/shares?include_revoked=true')
            shares = r.json()['shares']
            assert len(shares) == 1
            assert shares[0]['is_revoked'] is True

    @pytest.mark.asyncio
    async def test_list_shows_active_status(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await c.post('/w/ws_1/api/v1/shares', json={'path': '/a.txt'})
            r = await c.get('/w/ws_1/api/v1/shares')
            shares = r.json()['shares']
            assert shares[0]['is_active'] is True
            assert shares[0]['is_expired'] is False
            assert shares[0]['is_revoked'] is False


# =====================================================================
# Share revocation
# =====================================================================


class TestRevokeShare:
    """DELETE /w/{workspace_id}/api/v1/shares/{share_id}."""

    @pytest.mark.asyncio
    async def test_revoke_returns_metadata(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/shares', json={'path': '/a.txt'})
            sid = cr.json()['share_id']
            r = await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            assert r.status_code == 200
            data = r.json()
            assert data['share_id'] == sid
            assert data['is_active'] is False
            assert 'revoked_at' in data

    @pytest.mark.asyncio
    async def test_revoke_is_idempotent(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/shares', json={'path': '/a.txt'})
            sid = cr.json()['share_id']
            r1 = await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            r2 = await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            assert r1.json()['revoked_at'] == r2.json()['revoked_at']

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_returns_404(self, member_app):
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.delete('/w/ws_1/api/v1/shares/9999')
            assert r.status_code == 404
            assert r.json()['error'] == 'share_not_found'

    @pytest.mark.asyncio
    async def test_revoke_non_member_gets_403(self, no_member_app):
        transport = ASGITransport(app=no_member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.delete('/w/ws_1/api/v1/shares/1')
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_revoke_wrong_workspace_returns_404(self, member_app):
        """Share created in ws_1 but revoked via ws_2 path."""
        member_app.state.membership.add_member('ws_2', 'user_1')
        transport = ASGITransport(app=member_app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            cr = await c.post('/w/ws_1/api/v1/shares', json={'path': '/a.txt'})
            sid = cr.json()['share_id']
            r = await c.delete(f'/w/ws_2/api/v1/shares/{sid}')
            assert r.status_code == 404
