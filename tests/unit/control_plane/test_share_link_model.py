"""Tests for share-link domain model and repository.

Bead: bd-223o.12.1 (F1)

Validates:
  - Token generation produces unique, URL-safe tokens.
  - Token hashing is deterministic (SHA-256).
  - Plaintext token is never stored in the model or repository.
  - Share link lifecycle: create, resolve, expire, revoke.
  - Repository operations: create, get_by_hash, list, revoke, resolve.
  - Domain exceptions: not found, expired, revoked.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from control_plane.app.sharing.model import (
    InMemoryShareLinkRepository,
    ShareLink,
    ShareLinkExpired,
    ShareLinkNotFound,
    ShareLinkRevoked,
    generate_share_token,
    hash_token,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_link(
    workspace_id: str = 'ws_1',
    path: str = '/src/main.py',
    access: str = 'read',
    created_by: str = 'user_1',
    token: str | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, ShareLink]:
    """Create a share link with a generated token.

    Returns (plaintext_token, ShareLink).
    """
    plaintext = token or generate_share_token()
    expires = _now() + (expires_delta or timedelta(hours=72))
    link = ShareLink(
        id=0,  # Assigned by repository.
        workspace_id=workspace_id,
        path=path,
        token_hash=hash_token(plaintext),
        access=access,
        created_by=created_by,
        expires_at=expires,
    )
    return plaintext, link


@pytest.fixture
def repo():
    return InMemoryShareLinkRepository()


# =====================================================================
# Token operations
# =====================================================================


class TestTokenGeneration:
    """Token generation and hashing."""

    def test_generate_produces_nonempty_string(self):
        token = generate_share_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_tokens_are_unique(self):
        tokens = {generate_share_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_token_is_url_safe(self):
        token = generate_share_token()
        # URL-safe base64 uses only these characters.
        allowed = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=')
        assert all(c in allowed for c in token)

    def test_hash_is_deterministic(self):
        token = 'test_token_123'
        h1 = hash_token(token)
        h2 = hash_token(token)
        assert h1 == h2

    def test_hash_is_hex_sha256(self):
        h = hash_token('hello')
        assert len(h) == 64  # SHA-256 hex is 64 chars.
        assert all(c in '0123456789abcdef' for c in h)

    def test_different_tokens_produce_different_hashes(self):
        h1 = hash_token('token_a')
        h2 = hash_token('token_b')
        assert h1 != h2


# =====================================================================
# ShareLink domain model
# =====================================================================


class TestShareLinkModel:
    """ShareLink properties and lifecycle flags."""

    def test_active_link(self):
        _, link = _make_link(expires_delta=timedelta(hours=1))
        assert link.is_active is True
        assert link.is_expired is False
        assert link.is_revoked is False

    def test_expired_link(self):
        _, link = _make_link(expires_delta=timedelta(hours=-1))
        assert link.is_expired is True
        assert link.is_active is False

    def test_revoked_link(self):
        _, link = _make_link()
        link.revoked_at = _now()
        assert link.is_revoked is True
        assert link.is_active is False

    def test_both_expired_and_revoked(self):
        _, link = _make_link(expires_delta=timedelta(hours=-1))
        link.revoked_at = _now()
        assert link.is_active is False

    def test_access_modes(self):
        _, read_link = _make_link(access='read')
        _, write_link = _make_link(access='write')
        assert read_link.access == 'read'
        assert write_link.access == 'write'


# =====================================================================
# InMemoryShareLinkRepository
# =====================================================================


class TestRepositoryCreate:
    """Repository create operations."""

    @pytest.mark.asyncio
    async def test_create_assigns_id(self, repo):
        _, link = _make_link()
        created = await repo.create(link)
        assert created.id > 0

    @pytest.mark.asyncio
    async def test_create_sequential_ids(self, repo):
        _, link1 = _make_link()
        _, link2 = _make_link()
        c1 = await repo.create(link1)
        c2 = await repo.create(link2)
        assert c2.id == c1.id + 1


class TestRepositoryGetByHash:
    """Repository lookup by token hash."""

    @pytest.mark.asyncio
    async def test_get_existing(self, repo):
        token, link = _make_link()
        await repo.create(link)
        found = await repo.get_by_token_hash(hash_token(token))
        assert found is not None
        assert found.workspace_id == 'ws_1'

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, repo):
        found = await repo.get_by_token_hash(hash_token('nonexistent'))
        assert found is None


class TestRepositoryList:
    """Repository listing operations."""

    @pytest.mark.asyncio
    async def test_list_by_workspace(self, repo):
        _, l1 = _make_link(workspace_id='ws_1')
        _, l2 = _make_link(workspace_id='ws_1')
        _, l3 = _make_link(workspace_id='ws_2')
        for l in (l1, l2, l3):
            await repo.create(l)

        ws1_links = await repo.list_for_workspace('ws_1')
        assert len(ws1_links) == 2
        assert all(l.workspace_id == 'ws_1' for l in ws1_links)

    @pytest.mark.asyncio
    async def test_list_excludes_revoked_by_default(self, repo):
        _, l1 = _make_link(workspace_id='ws_1')
        _, l2 = _make_link(workspace_id='ws_1')
        await repo.create(l1)
        await repo.create(l2)
        await repo.revoke(l1.id, 'ws_1')

        ws1_links = await repo.list_for_workspace('ws_1')
        assert len(ws1_links) == 1

    @pytest.mark.asyncio
    async def test_list_includes_revoked_when_requested(self, repo):
        _, l1 = _make_link(workspace_id='ws_1')
        _, l2 = _make_link(workspace_id='ws_1')
        await repo.create(l1)
        await repo.create(l2)
        await repo.revoke(l1.id, 'ws_1')

        ws1_links = await repo.list_for_workspace(
            'ws_1', include_revoked=True,
        )
        assert len(ws1_links) == 2

    @pytest.mark.asyncio
    async def test_list_empty_workspace(self, repo):
        links = await repo.list_for_workspace('ws_nonexistent')
        assert links == []


class TestRepositoryRevoke:
    """Repository revoke operations."""

    @pytest.mark.asyncio
    async def test_revoke_sets_revoked_at(self, repo):
        _, link = _make_link(workspace_id='ws_1')
        await repo.create(link)
        revoked = await repo.revoke(link.id, 'ws_1')
        assert revoked is not None
        assert revoked.revoked_at is not None
        assert revoked.is_revoked is True

    @pytest.mark.asyncio
    async def test_revoke_is_idempotent(self, repo):
        _, link = _make_link(workspace_id='ws_1')
        await repo.create(link)
        r1 = await repo.revoke(link.id, 'ws_1')
        first_revoked_at = r1.revoked_at
        r2 = await repo.revoke(link.id, 'ws_1')
        assert r2.revoked_at == first_revoked_at

    @pytest.mark.asyncio
    async def test_revoke_wrong_workspace_returns_none(self, repo):
        _, link = _make_link(workspace_id='ws_1')
        await repo.create(link)
        result = await repo.revoke(link.id, 'ws_other')
        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_missing_returns_none(self, repo):
        result = await repo.revoke(999, 'ws_1')
        assert result is None


class TestRepositoryResolveToken:
    """Repository token resolution with exception handling."""

    @pytest.mark.asyncio
    async def test_resolve_active_token(self, repo):
        token, link = _make_link()
        await repo.create(link)
        resolved = await repo.resolve_token(token)
        assert resolved.workspace_id == 'ws_1'
        assert resolved.path == '/src/main.py'

    @pytest.mark.asyncio
    async def test_resolve_unknown_token_raises(self, repo):
        with pytest.raises(ShareLinkNotFound):
            await repo.resolve_token('nonexistent_token')

    @pytest.mark.asyncio
    async def test_resolve_expired_token_raises(self, repo):
        token, link = _make_link(expires_delta=timedelta(hours=-1))
        await repo.create(link)
        with pytest.raises(ShareLinkExpired) as exc_info:
            await repo.resolve_token(token)
        assert exc_info.value.share_id == link.id

    @pytest.mark.asyncio
    async def test_resolve_revoked_token_raises(self, repo):
        token, link = _make_link()
        await repo.create(link)
        await repo.revoke(link.id, 'ws_1')
        with pytest.raises(ShareLinkRevoked) as exc_info:
            await repo.resolve_token(token)
        assert exc_info.value.share_id == link.id

    @pytest.mark.asyncio
    async def test_revoked_checked_before_expired(self, repo):
        """If both revoked and expired, ShareLinkRevoked takes precedence."""
        token, link = _make_link(expires_delta=timedelta(hours=-1))
        await repo.create(link)
        await repo.revoke(link.id, 'ws_1')
        with pytest.raises(ShareLinkRevoked):
            await repo.resolve_token(token)


# =====================================================================
# Security: plaintext token never stored
# =====================================================================


class TestPlaintextNeverStored:
    """Critical security invariant: plaintext token never persisted."""

    @pytest.mark.asyncio
    async def test_model_has_no_plaintext_field(self):
        """ShareLink has no attribute containing the plaintext token."""
        _, link = _make_link(token='secret_plaintext')
        # Check that no field value contains the plaintext.
        for attr in ('id', 'workspace_id', 'path', 'token_hash', 'access',
                      'created_by', 'expires_at', 'revoked_at', 'created_at'):
            value = str(getattr(link, attr))
            assert 'secret_plaintext' not in value, (
                f'Plaintext token found in ShareLink.{attr}'
            )

    @pytest.mark.asyncio
    async def test_token_hash_is_not_reversible(self):
        """The stored hash cannot be trivially reversed to the plaintext."""
        token = generate_share_token()
        h = hash_token(token)
        assert token not in h
        assert h != token
        assert len(h) == 64  # SHA-256 hex digest.

    @pytest.mark.asyncio
    async def test_repository_stores_only_hash(self, repo):
        """Repository internal state must not contain the plaintext."""
        token, link = _make_link(token='super_secret_token_value')
        await repo.create(link)

        # Inspect repository internals.
        for stored_link in repo._links.values():
            assert 'super_secret_token_value' not in str(stored_link.token_hash)
            assert stored_link.token_hash == hash_token('super_secret_token_value')
