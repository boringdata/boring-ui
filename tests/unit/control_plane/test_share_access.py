"""Tests for share-link read/write access endpoints.

Bead: bd-223o.12.3 (F3)

Validates:
  - Read via valid share token returns file metadata.
  - Write via valid write-share token succeeds.
  - Read-only share rejects write with 403.
  - Exact-path enforcement rejects mismatched paths.
  - Expired token returns 410.
  - Revoked/unknown token returns 404.
  - Path traversal in write body rejected.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from control_plane.app.sharing.model import (
    InMemoryShareLinkRepository,
    ShareLink,
    generate_share_token,
    hash_token,
)
from control_plane.app.sharing.access import (
    create_share_access_router,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _make_app() -> tuple[FastAPI, InMemoryShareLinkRepository]:
    """Build a test app with share access routes."""
    app = FastAPI()
    repo = InMemoryShareLinkRepository()
    router = create_share_access_router(repo)
    app.include_router(router)
    return app, repo


async def _create_link(
    repo: InMemoryShareLinkRepository,
    *,
    path: str = '/docs/README.md',
    access: str = 'read',
    workspace_id: str = 'ws_1',
    expired: bool = False,
    revoked: bool = False,
) -> tuple[str, ShareLink]:
    """Create a share link and return (plaintext_token, link)."""
    plaintext = generate_share_token()
    now = datetime.now(timezone.utc)

    if expired:
        expires_at = now - timedelta(hours=1)
    else:
        expires_at = now + timedelta(hours=72)

    link = ShareLink(
        id=0,
        workspace_id=workspace_id,
        path=path,
        token_hash=hash_token(plaintext),
        access=access,
        created_by='user_1',
        expires_at=expires_at,
        revoked_at=now if revoked else None,
        created_at=now,
    )
    link = await repo.create(link)
    return plaintext, link


@pytest.fixture
def app_and_repo():
    return _make_app()


# =====================================================================
# Read share (GET /api/v1/shares/{token})
# =====================================================================


class TestReadShare:
    """GET /api/v1/shares/{token}."""

    @pytest.mark.asyncio
    async def test_read_valid_token(self, app_and_repo):
        app, repo = app_and_repo
        token, link = await _create_link(repo)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get(f'/api/v1/shares/{token}')
            assert r.status_code == 200
            data = r.json()
            assert data['workspace_id'] == 'ws_1'
            assert data['path'] == '/docs/README.md'
            assert data['access'] == 'read'

    @pytest.mark.asyncio
    async def test_read_write_share_also_works(self, app_and_repo):
        app, repo = app_and_repo
        token, link = await _create_link(repo, access='write')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get(f'/api/v1/shares/{token}')
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_read_unknown_token_returns_404(self, app_and_repo):
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/api/v1/shares/totally_fake_token')
            assert r.status_code == 404
            assert r.json()['error'] == 'share_not_found'

    @pytest.mark.asyncio
    async def test_read_expired_token_returns_410(self, app_and_repo):
        app, repo = app_and_repo
        token, _ = await _create_link(repo, expired=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get(f'/api/v1/shares/{token}')
            assert r.status_code == 410
            assert r.json()['error'] == 'share_expired'

    @pytest.mark.asyncio
    async def test_read_revoked_token_returns_404(self, app_and_repo):
        app, repo = app_and_repo
        token, _ = await _create_link(repo, revoked=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get(f'/api/v1/shares/{token}')
            assert r.status_code == 404
            assert r.json()['error'] == 'share_not_found'


# =====================================================================
# Write share (PUT /api/v1/shares/{token})
# =====================================================================


class TestWriteShare:
    """PUT /api/v1/shares/{token}."""

    @pytest.mark.asyncio
    async def test_write_valid_token(self, app_and_repo):
        app, repo = app_and_repo
        token, link = await _create_link(repo, access='write')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs/README.md', 'content': 'updated'},
            )
            assert r.status_code == 200
            assert r.json()['status'] == 'ok'

    @pytest.mark.asyncio
    async def test_write_read_only_share_returns_403(self, app_and_repo):
        app, repo = app_and_repo
        token, _ = await _create_link(repo, access='read')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs/README.md', 'content': 'nope'},
            )
            assert r.status_code == 403
            assert r.json()['error'] == 'share_scope_violation'

    @pytest.mark.asyncio
    async def test_write_path_mismatch_returns_403(self, app_and_repo):
        app, repo = app_and_repo
        token, _ = await _create_link(
            repo, access='write', path='/docs/README.md',
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/other/file.txt', 'content': 'nope'},
            )
            assert r.status_code == 403
            assert r.json()['error'] == 'share_scope_violation'

    @pytest.mark.asyncio
    async def test_write_traversal_path_rejected(self, app_and_repo):
        app, repo = app_and_repo
        token, _ = await _create_link(repo, access='write')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs/../../etc/passwd', 'content': 'bad'},
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'invalid_path'

    @pytest.mark.asyncio
    async def test_write_relative_path_rejected(self, app_and_repo):
        app, repo = app_and_repo
        token, _ = await _create_link(repo, access='write')
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': 'docs/README.md', 'content': 'bad'},
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'invalid_path'

    @pytest.mark.asyncio
    async def test_write_unknown_token_returns_404(self, app_and_repo):
        app, repo = app_and_repo
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                '/api/v1/shares/totally_fake',
                json={'path': '/file.txt', 'content': 'x'},
            )
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_write_expired_token_returns_410(self, app_and_repo):
        app, repo = app_and_repo
        token, _ = await _create_link(repo, access='write', expired=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs/README.md', 'content': 'late'},
            )
            assert r.status_code == 410

    @pytest.mark.asyncio
    async def test_write_revoked_token_returns_404(self, app_and_repo):
        app, repo = app_and_repo
        token, _ = await _create_link(repo, access='write', revoked=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs/README.md', 'content': 'revoked'},
            )
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_write_normalized_path_matches(self, app_and_repo):
        """Path with extra slashes still matches if normalized form equals share path."""
        app, repo = app_and_repo
        token, _ = await _create_link(
            repo, access='write', path='/docs/README.md',
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs//README.md', 'content': 'ok'},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_write_empty_content_allowed(self, app_and_repo):
        """Empty content is valid (clears the file)."""
        app, repo = app_and_repo
        token, _ = await _create_link(
            repo, access='write', path='/docs/README.md',
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs/README.md', 'content': ''},
            )
            assert r.status_code == 200
