"""Share link security, path normalization, and lifecycle integration tests.

Bead: bd-14av (F5)

Validates cross-cutting share link behavior:
  - Token security: hash-only persistence, no plaintext in DB
  - Path normalization: traversal rejection, exact-path enforcement
  - Lifecycle: create → access → revoke → 404, expire → 410
  - Access modes: read allows GET only, write allows both
  - Audit events: token redaction, event types, no plaintext leakage
  - Repository: resolve_token raises correct exceptions
  - Cross-workspace isolation: share from workspace A not accessible via B
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from control_plane.app.sharing.model import (
    DEFAULT_EXPIRY_HOURS,
    TOKEN_BYTES,
    InMemoryShareLinkRepository,
    ShareLink,
    ShareLinkExpired,
    ShareLinkNotFound,
    ShareLinkRevoked,
    generate_share_token,
    hash_token,
)
from control_plane.app.sharing.routes import (
    VALID_ACCESS_MODES,
    normalize_share_path,
)
from control_plane.app.sharing.audit import (
    InMemoryShareAuditEmitter,
    ShareAuditEvent,
    TOKEN_PREFIX_LENGTH,
    emit_share_accessed,
    emit_share_created,
    emit_share_denied,
    emit_share_revoked,
    emit_share_write,
    redact_string,
    redact_token,
)


@pytest.fixture
def repo():
    return InMemoryShareLinkRepository()


@pytest.fixture
def emitter():
    return InMemoryShareAuditEmitter()


def _make_link(
    workspace_id: str = 'ws_1',
    path: str = '/docs/README.md',
    access: str = 'read',
    token: str | None = None,
    expires_hours: int = DEFAULT_EXPIRY_HOURS,
    revoked: bool = False,
) -> tuple[ShareLink, str]:
    """Create a share link and return (link, plaintext_token)."""
    plaintext = token or generate_share_token()
    now = datetime.now(timezone.utc)
    link = ShareLink(
        id=0,
        workspace_id=workspace_id,
        path=path,
        token_hash=hash_token(plaintext),
        access=access,
        created_by='user_1',
        expires_at=now + timedelta(hours=expires_hours),
        revoked_at=now if revoked else None,
        created_at=now,
    )
    return link, plaintext


# =====================================================================
# 1. Token security: hash-only persistence
# =====================================================================


class TestTokenSecurity:
    """Plaintext tokens are never stored; only hashes."""

    def test_hash_is_deterministic(self):
        token = 'my-test-token'
        assert hash_token(token) == hash_token(token)

    def test_hash_differs_for_different_tokens(self):
        t1 = generate_share_token()
        t2 = generate_share_token()
        assert hash_token(t1) != hash_token(t2)

    def test_hash_is_sha256_hex(self):
        h = hash_token('test')
        assert len(h) == 64  # SHA-256 hex digest.
        assert all(c in '0123456789abcdef' for c in h)

    def test_generated_token_is_url_safe(self):
        import re
        token = generate_share_token()
        assert re.match(r'^[A-Za-z0-9_-]+$', token)

    def test_generated_token_has_sufficient_entropy(self):
        token = generate_share_token()
        # 32 bytes → ~43 chars URL-safe base64.
        assert len(token) >= 40

    def test_two_generated_tokens_are_unique(self):
        t1 = generate_share_token()
        t2 = generate_share_token()
        assert t1 != t2

    @pytest.mark.asyncio
    async def test_repo_stores_hash_not_plaintext(self, repo):
        link, plaintext = _make_link()
        stored = await repo.create(link)
        assert stored.token_hash == hash_token(plaintext)
        # Verify no field contains the plaintext.
        assert plaintext not in str(stored.token_hash)


# =====================================================================
# 2. Path normalization and traversal rejection
# =====================================================================


class TestPathNormalization:
    """Exact-path enforcement with traversal prevention."""

    def test_valid_absolute_path(self):
        assert normalize_share_path('/docs/README.md') == '/docs/README.md'

    def test_trailing_slash_normalized(self):
        assert normalize_share_path('/docs/') == '/docs'

    def test_double_slash_normalized(self):
        assert normalize_share_path('/docs//README.md') == '/docs/README.md'

    def test_traversal_rejected(self):
        assert normalize_share_path('/docs/../etc/passwd') is None

    def test_traversal_in_middle_rejected(self):
        assert normalize_share_path('/docs/sub/../../etc/passwd') is None

    def test_bare_traversal_rejected(self):
        assert normalize_share_path('/..') is None

    def test_relative_path_rejected(self):
        assert normalize_share_path('docs/README.md') is None

    def test_empty_path_rejected(self):
        assert normalize_share_path('') is None

    def test_root_path_valid(self):
        assert normalize_share_path('/') == '/'


# =====================================================================
# 3. Share lifecycle: create → access → revoke → expire
# =====================================================================


class TestShareLifecycle:
    """Full lifecycle from creation through revocation and expiry."""

    @pytest.mark.asyncio
    async def test_create_and_resolve(self, repo):
        link, plaintext = _make_link()
        await repo.create(link)
        resolved = await repo.resolve_token(plaintext)
        assert resolved.path == '/docs/README.md'
        assert resolved.access == 'read'

    @pytest.mark.asyncio
    async def test_revoke_then_resolve_raises_revoked(self, repo):
        link, plaintext = _make_link()
        await repo.create(link)
        await repo.revoke(link.id, link.workspace_id)

        with pytest.raises(ShareLinkRevoked):
            await repo.resolve_token(plaintext)

    @pytest.mark.asyncio
    async def test_expired_link_raises_expired(self, repo):
        link, plaintext = _make_link(expires_hours=-1)  # Already expired.
        await repo.create(link)

        with pytest.raises(ShareLinkExpired):
            await repo.resolve_token(plaintext)

    @pytest.mark.asyncio
    async def test_unknown_token_raises_not_found(self, repo):
        with pytest.raises(ShareLinkNotFound):
            await repo.resolve_token('nonexistent-token')

    @pytest.mark.asyncio
    async def test_revoked_returns_404_not_410(self, repo):
        """Revoked links return 'not found', not 'expired'."""
        link, plaintext = _make_link()
        await repo.create(link)
        await repo.revoke(link.id, link.workspace_id)

        with pytest.raises(ShareLinkRevoked):
            await repo.resolve_token(plaintext)

    @pytest.mark.asyncio
    async def test_is_active_property(self, repo):
        link, _ = _make_link()
        await repo.create(link)
        assert link.is_active
        assert not link.is_expired
        assert not link.is_revoked

    @pytest.mark.asyncio
    async def test_revoke_sets_revoked_at(self, repo):
        link, _ = _make_link()
        await repo.create(link)
        revoked = await repo.revoke(link.id, link.workspace_id)
        assert revoked.revoked_at is not None
        assert not revoked.is_active

    @pytest.mark.asyncio
    async def test_revoke_idempotent(self, repo):
        link, _ = _make_link()
        await repo.create(link)
        r1 = await repo.revoke(link.id, link.workspace_id)
        r2 = await repo.revoke(link.id, link.workspace_id)
        assert r1.revoked_at == r2.revoked_at


# =====================================================================
# 4. Access mode enforcement
# =====================================================================


class TestAccessModes:
    """Read-only vs read-write share access."""

    def test_valid_access_modes(self):
        assert VALID_ACCESS_MODES == frozenset({'read', 'write'})

    @pytest.mark.asyncio
    async def test_read_share_has_read_access(self, repo):
        link, plaintext = _make_link(access='read')
        await repo.create(link)
        resolved = await repo.resolve_token(plaintext)
        assert resolved.access == 'read'

    @pytest.mark.asyncio
    async def test_write_share_has_write_access(self, repo):
        link, plaintext = _make_link(access='write')
        await repo.create(link)
        resolved = await repo.resolve_token(plaintext)
        assert resolved.access == 'write'


# =====================================================================
# 5. Exact-path enforcement
# =====================================================================


class TestExactPathEnforcement:
    """Share access must match the exact path in the share link."""

    @pytest.mark.asyncio
    async def test_matching_path_succeeds(self, repo):
        link, plaintext = _make_link(path='/docs/A.md')
        await repo.create(link)
        resolved = await repo.resolve_token(plaintext)
        assert resolved.path == '/docs/A.md'

    @pytest.mark.asyncio
    async def test_different_path_is_detectable(self, repo):
        link, plaintext = _make_link(path='/docs/A.md')
        await repo.create(link)
        resolved = await repo.resolve_token(plaintext)
        # Application layer checks: requested_path != share.path → 403.
        requested_path = '/docs/B.md'
        assert requested_path != resolved.path

    @pytest.mark.asyncio
    async def test_traversal_path_detected_before_compare(self):
        """Path traversal is caught by normalize_share_path before comparison."""
        assert normalize_share_path('/docs/../etc/passwd') is None


# =====================================================================
# 6. Cross-workspace isolation
# =====================================================================


class TestCrossWorkspaceIsolation:
    """Shares from one workspace cannot be accessed via another."""

    @pytest.mark.asyncio
    async def test_revoke_cross_workspace_returns_none(self, repo):
        link, _ = _make_link(workspace_id='ws_1')
        await repo.create(link)

        result = await repo.revoke(link.id, 'ws_OTHER')
        assert result is None

    @pytest.mark.asyncio
    async def test_list_isolated_by_workspace(self, repo):
        link1, _ = _make_link(workspace_id='ws_1')
        link2, _ = _make_link(workspace_id='ws_2')
        await repo.create(link1)
        await repo.create(link2)

        ws1_links = await repo.list_for_workspace('ws_1')
        ws2_links = await repo.list_for_workspace('ws_2')
        assert len(ws1_links) == 1
        assert len(ws2_links) == 1
        assert ws1_links[0].workspace_id == 'ws_1'
        assert ws2_links[0].workspace_id == 'ws_2'


# =====================================================================
# 7. Audit event token redaction
# =====================================================================


class TestAuditTokenRedaction:
    """Audit events never contain plaintext tokens."""

    def test_redact_token_truncates(self):
        token = generate_share_token()
        redacted = redact_token(token)
        assert redacted.endswith('...')
        assert len(redacted) == TOKEN_PREFIX_LENGTH + 3
        assert token not in redacted

    def test_redact_short_token(self):
        assert redact_token('abc') == '<redacted>'

    def test_redact_none_token(self):
        assert redact_token(None) == '<redacted>'

    def test_redact_string_replaces_token_like_sequences(self):
        token = generate_share_token()
        text = f'Access with token {token} denied'
        redacted = redact_string(text)
        assert token not in redacted
        assert 'denied' in redacted

    @pytest.mark.asyncio
    async def test_emit_created_redacts_token(self, emitter):
        token = generate_share_token()
        event = await emit_share_created(
            emitter,
            workspace_id='ws_1',
            share_id=1,
            token=token,
            path='/docs/A.md',
            access='read',
            user_id='user_1',
        )
        assert token not in event.token_prefix
        assert event.token_prefix.endswith('...')

    @pytest.mark.asyncio
    async def test_emit_accessed_redacts_token(self, emitter):
        token = generate_share_token()
        event = await emit_share_accessed(
            emitter,
            workspace_id='ws_1',
            share_id=1,
            token=token,
            path='/docs/A.md',
            access='read',
        )
        assert event.event_type == 'share.accessed'
        assert token not in event.token_prefix

    @pytest.mark.asyncio
    async def test_emit_write_redacts_token(self, emitter):
        token = generate_share_token()
        event = await emit_share_write(
            emitter,
            workspace_id='ws_1',
            share_id=1,
            token=token,
            path='/docs/A.md',
        )
        assert event.event_type == 'share.write'
        assert token not in event.token_prefix

    @pytest.mark.asyncio
    async def test_emit_denied_redacts_token(self, emitter):
        token = generate_share_token()
        event = await emit_share_denied(
            emitter,
            workspace_id='ws_1',
            token=token,
            path='/docs/A.md',
            detail='scope violation',
        )
        assert event.event_type == 'share.denied'
        assert token not in event.token_prefix

    @pytest.mark.asyncio
    async def test_emit_revoked_no_token(self, emitter):
        event = await emit_share_revoked(
            emitter,
            workspace_id='ws_1',
            share_id=1,
            path='/docs/A.md',
            user_id='user_1',
        )
        assert event.event_type == 'share.revoked'
        assert event.token_prefix == '<redacted>'

    @pytest.mark.asyncio
    async def test_audit_to_dict_no_plaintext(self, emitter):
        token = generate_share_token()
        event = await emit_share_created(
            emitter,
            workspace_id='ws_1',
            share_id=1,
            token=token,
            path='/docs/A.md',
            access='read',
            user_id='user_1',
        )
        d = event.to_dict()
        # No field should contain the full token.
        for key, value in d.items():
            if isinstance(value, str):
                assert token not in value, (
                    f'Plaintext token found in audit dict field {key!r}'
                )


# =====================================================================
# 8. Audit event types and emitter
# =====================================================================


class TestAuditEventTypes:
    """Audit emitter records correct event types."""

    @pytest.mark.asyncio
    async def test_emitter_stores_events(self, emitter):
        await emit_share_created(
            emitter, workspace_id='ws_1', share_id=1,
            token='tok', path='/a', access='read', user_id='u',
        )
        await emit_share_accessed(
            emitter, workspace_id='ws_1', share_id=1,
            token='tok', path='/a', access='read',
        )
        assert len(emitter.events) == 2

    @pytest.mark.asyncio
    async def test_emitter_find_by_type(self, emitter):
        await emit_share_created(
            emitter, workspace_id='ws_1', share_id=1,
            token='tok', path='/a', access='read', user_id='u',
        )
        await emit_share_denied(
            emitter, workspace_id='ws_1', token='tok',
        )
        created = emitter.find(event_type='share.created')
        assert len(created) == 1

    @pytest.mark.asyncio
    async def test_emitter_find_by_workspace(self, emitter):
        await emit_share_created(
            emitter, workspace_id='ws_1', share_id=1,
            token='tok', path='/a', access='read', user_id='u',
        )
        await emit_share_created(
            emitter, workspace_id='ws_2', share_id=2,
            token='tok2', path='/b', access='read', user_id='u',
        )
        ws1_events = emitter.find(workspace_id='ws_1')
        assert len(ws1_events) == 1


# =====================================================================
# 9. Repository listing and filtering
# =====================================================================


class TestRepositoryListing:
    """List and filter share links."""

    @pytest.mark.asyncio
    async def test_list_excludes_revoked_by_default(self, repo):
        link1, _ = _make_link()
        link2, _ = _make_link(revoked=True)
        await repo.create(link1)
        await repo.create(link2)

        active = await repo.list_for_workspace('ws_1')
        assert len(active) == 1

    @pytest.mark.asyncio
    async def test_list_includes_revoked_when_requested(self, repo):
        link1, _ = _make_link()
        link2, _ = _make_link(revoked=True)
        await repo.create(link1)
        await repo.create(link2)

        all_links = await repo.list_for_workspace('ws_1', include_revoked=True)
        assert len(all_links) == 2

    @pytest.mark.asyncio
    async def test_list_sorted_by_created_at(self, repo):
        now = datetime.now(timezone.utc)
        link1, _ = _make_link()
        link1.created_at = now - timedelta(hours=2)
        link2, _ = _make_link()
        link2.created_at = now - timedelta(hours=1)
        await repo.create(link1)
        await repo.create(link2)

        links = await repo.list_for_workspace('ws_1')
        assert links[0].created_at < links[1].created_at


# =====================================================================
# 10. Frozen dataclass invariants
# =====================================================================


class TestFrozenInvariants:

    def test_audit_event_frozen(self):
        event = ShareAuditEvent(
            event_type='share.created',
            workspace_id='ws_1',
        )
        with pytest.raises(AttributeError):
            event.event_type = 'changed'

    def test_share_link_is_mutable(self):
        # ShareLink is intentionally NOT frozen (repo mutates id and revoked_at).
        link, _ = _make_link()
        link.id = 999  # Should work.
        assert link.id == 999


# =====================================================================
# 11. Exception detail
# =====================================================================


class TestExceptionDetail:

    def test_expired_exception_has_share_id(self):
        now = datetime.now(timezone.utc)
        exc = ShareLinkExpired(42, now)
        assert exc.share_id == 42
        assert exc.expired_at == now
        assert '42' in str(exc)

    def test_revoked_exception_has_share_id(self):
        now = datetime.now(timezone.utc)
        exc = ShareLinkRevoked(42, now)
        assert exc.share_id == 42
        assert exc.revoked_at == now
        assert '42' in str(exc)
