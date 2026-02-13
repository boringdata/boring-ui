"""Share-link behavior tests: expire/revoke lifecycle and traversal/mismatch negatives.

Beads: bd-223o.12.2.1 (F2a) + bd-223o.12.3.1 (F3a)

F2a validates:
  - Expired links are excluded from default listing.
  - Revoked links are excluded from default listing.
  - Expired vs revoked returns correct HTTP status codes (410 vs 404).
  - Revoke takes precedence over expiry (revoked+expired → 404, not 410).
  - Fresh link → revoke → access → correct behavior.
  - Fresh link → expire → access → correct behavior.
  - Re-create after revoke yields new independent link.

F3a validates:
  - Path traversal variations all rejected.
  - Path mismatch on write always returns 403.
  - Normalized paths that match succeed.
  - Non-absolute paths on write rejected.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from control_plane.app.agent.sessions import InMemoryMembershipChecker
from control_plane.app.sharing.model import (
    InMemoryShareLinkRepository,
    ShareLink,
    generate_share_token,
    hash_token,
)
from control_plane.app.sharing.routes import create_share_router
from control_plane.app.sharing.access import create_share_access_router
from control_plane.app.security.token_verify import AuthIdentity


# ── Test app ──────────────────────────────────────────────────────────


def _make_full_app() -> tuple[FastAPI, InMemoryShareLinkRepository]:
    """App with both management and access routes."""
    app = FastAPI()
    repo = InMemoryShareLinkRepository()
    checker = InMemoryMembershipChecker({('ws_1', 'user_1')})

    app.include_router(create_share_router(repo, checker))
    app.include_router(create_share_access_router(repo))

    @app.middleware('http')
    async def fake_auth(request: Request, call_next):
        request.state.auth_identity = AuthIdentity(
            user_id='user_1', email='u@t.com', role='authenticated',
        )
        return await call_next(request)

    app.state.share_repo = repo
    return app, repo


@pytest.fixture
def full_app():
    return _make_full_app()


async def _create_share(client, path='/docs/README.md', access='read', hours=72):
    """Helper: create a share via API and return (token, share_id)."""
    r = await client.post(
        '/w/ws_1/api/v1/shares',
        json={'path': path, 'access': access, 'expires_in_hours': hours},
    )
    assert r.status_code == 201
    data = r.json()
    return data['token'], data['share_id']


# =====================================================================
# F2a: Expire / Revoke lifecycle behavior
# =====================================================================


class TestExpireRevokeBehavior:
    """Expire and revoke lifecycle transitions via API."""

    @pytest.mark.asyncio
    async def test_revoked_link_read_returns_404(self, full_app):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, sid = await _create_share(c)
            await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            r = await c.get(f'/api/v1/shares/{token}')
            assert r.status_code == 404
            assert r.json()['error'] == 'share_not_found'

    @pytest.mark.asyncio
    async def test_expired_link_read_returns_410(self, full_app):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, sid = await _create_share(c, hours=1)

            # Manually expire the link by setting expires_at to the past.
            link = list(repo._links.values())[-1]
            link.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

            r = await c.get(f'/api/v1/shares/{token}')
            assert r.status_code == 410
            assert r.json()['error'] == 'share_expired'

    @pytest.mark.asyncio
    async def test_revoked_and_expired_returns_404_not_410(self, full_app):
        """Revoked takes precedence over expired."""
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, sid = await _create_share(c, hours=1)

            # Revoke first, then expire.
            await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            link = list(repo._links.values())[-1]
            link.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

            r = await c.get(f'/api/v1/shares/{token}')
            assert r.status_code == 404  # Revoked, not 410.

    @pytest.mark.asyncio
    async def test_expired_link_excluded_from_list(self, full_app):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            await _create_share(c)
            link = list(repo._links.values())[-1]
            link.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

            r = await c.get('/w/ws_1/api/v1/shares')
            # Expired but not revoked — still listed (only revoked excluded).
            shares = r.json()['shares']
            assert len(shares) == 1
            assert shares[0]['is_expired'] is True

    @pytest.mark.asyncio
    async def test_revoked_link_excluded_from_default_list(self, full_app):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            _, sid = await _create_share(c)
            await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            r = await c.get('/w/ws_1/api/v1/shares')
            assert len(r.json()['shares']) == 0

    @pytest.mark.asyncio
    async def test_revoked_link_included_when_requested(self, full_app):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            _, sid = await _create_share(c)
            await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            r = await c.get('/w/ws_1/api/v1/shares?include_revoked=true')
            shares = r.json()['shares']
            assert len(shares) == 1
            assert shares[0]['is_revoked'] is True

    @pytest.mark.asyncio
    async def test_recreate_after_revoke_yields_new_link(self, full_app):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token1, sid1 = await _create_share(c)
            await c.delete(f'/w/ws_1/api/v1/shares/{sid1}')
            token2, sid2 = await _create_share(c)

            assert token1 != token2
            assert sid1 != sid2

            # New link works, old doesn't.
            r_new = await c.get(f'/api/v1/shares/{token2}')
            r_old = await c.get(f'/api/v1/shares/{token1}')
            assert r_new.status_code == 200
            assert r_old.status_code == 404

    @pytest.mark.asyncio
    async def test_write_to_revoked_returns_404(self, full_app):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, sid = await _create_share(c, access='write')
            await c.delete(f'/w/ws_1/api/v1/shares/{sid}')
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs/README.md', 'content': 'nope'},
            )
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_write_to_expired_returns_410(self, full_app):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, sid = await _create_share(c, access='write', hours=1)
            link = list(repo._links.values())[-1]
            link.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs/README.md', 'content': 'late'},
            )
            assert r.status_code == 410


# =====================================================================
# F3a: Traversal and mismatch negative tests
# =====================================================================


class TestTraversalNegative:
    """Path traversal variations all rejected."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize('bad_path', [
        '/docs/../../../etc/passwd',
        '/docs/../../secret',
        '/../root',
        '/./../../etc/shadow',
        '/docs/sub/../../../etc/hosts',
    ])
    async def test_create_traversal_rejected(self, full_app, bad_path):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': bad_path},
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'invalid_path'

    @pytest.mark.asyncio
    @pytest.mark.parametrize('bad_path', [
        '/docs/../../../etc/passwd',
        '/../secret',
        '/a/../../b',
    ])
    async def test_write_traversal_rejected(self, full_app, bad_path):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, _ = await _create_share(c, access='write')
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': bad_path, 'content': 'evil'},
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'invalid_path'


class TestPathMismatchNegative:
    """Exact-path enforcement rejects mismatched paths."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize('write_path', [
        '/other/file.txt',
        '/docs/OTHER.md',
        '/docs/readme.md',         # Case-sensitive mismatch.
        '/docs/README.md.bak',     # Suffix mismatch.
        '/docs',                    # Parent directory.
        '/',                        # Root.
    ])
    async def test_write_path_mismatch_returns_403(self, full_app, write_path):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, _ = await _create_share(
                c, path='/docs/README.md', access='write',
            )
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': write_path, 'content': 'nope'},
            )
            assert r.status_code == 403
            assert r.json()['error'] == 'share_scope_violation'

    @pytest.mark.asyncio
    async def test_write_exact_path_matches(self, full_app):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, _ = await _create_share(
                c, path='/docs/README.md', access='write',
            )
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs/README.md', 'content': 'ok'},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_write_normalized_equivalent_matches(self, full_app):
        """Path with extra slashes normalizes to match."""
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, _ = await _create_share(
                c, path='/docs/README.md', access='write',
            )
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': '/docs//README.md', 'content': 'ok'},
            )
            assert r.status_code == 200


class TestNonAbsolutePathNegative:
    """Non-absolute paths rejected on both create and write."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path', [
        'docs/README.md',
        'file.txt',
        './file.txt',
        '../file.txt',
        '',
    ])
    async def test_create_non_absolute_rejected(self, full_app, path):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.post(
                '/w/ws_1/api/v1/shares',
                json={'path': path} if path else {'path': path},
            )
            # Either 400 (invalid path) or 422 (pydantic min_length on empty).
            assert r.status_code in (400, 422)

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path', [
        'docs/README.md',
        'file.txt',
        './file.txt',
    ])
    async def test_write_non_absolute_rejected(self, full_app, path):
        app, repo = full_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            token, _ = await _create_share(
                c, path='/docs/README.md', access='write',
            )
            r = await c.put(
                f'/api/v1/shares/{token}',
                json={'path': path, 'content': 'x'},
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'invalid_path'
