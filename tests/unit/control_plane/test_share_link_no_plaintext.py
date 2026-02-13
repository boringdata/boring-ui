"""Persistence assertions: no plaintext share token storage.

Bead: bd-223o.12.1.1 (F1a)

Validates the critical security invariant that plaintext share tokens
never appear in persisted state:
  - No ShareLink field contains the plaintext
  - Repository internal storage uses only hashes
  - Serialized representations (str, repr, dict) don't leak
  - Bulk operations don't leak tokens
  - Token lifecycle (create, resolve, revoke) never exposes plaintext
  - Hash collision resistance: distinct tokens produce distinct hashes
  - Hash format invariants (SHA-256 hex, fixed length)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from control_plane.app.sharing.model import (
    InMemoryShareLinkRepository,
    ShareLink,
    ShareLinkExpired,
    ShareLinkNotFound,
    ShareLinkRevoked,
    TOKEN_BYTES,
    generate_share_token,
    hash_token,
)


def _now():
    return datetime.now(timezone.utc)


def _make_link(token=None, workspace_id='ws_1', **kwargs):
    plaintext = token or generate_share_token()
    defaults = dict(
        id=0,
        workspace_id=workspace_id,
        path='/file.py',
        token_hash=hash_token(plaintext),
        access='read',
        created_by='user_1',
        expires_at=_now() + timedelta(hours=72),
    )
    defaults.update(kwargs)
    return plaintext, ShareLink(**defaults)


@pytest.fixture
def repo():
    return InMemoryShareLinkRepository()


# =====================================================================
# 1. ShareLink model field inspection
# =====================================================================


class TestModelFieldInspection:
    """Inspect every ShareLink field for plaintext leakage."""

    def test_no_field_contains_plaintext(self):
        token, link = _make_link(token='PLAINTEXT_SECRET_TOKEN_XYZ')
        all_values = []
        for attr in vars(link):
            all_values.append(str(getattr(link, attr)))
        combined = ' '.join(all_values)
        assert 'PLAINTEXT_SECRET_TOKEN_XYZ' not in combined

    def test_token_hash_field_is_hex_digest(self):
        token, link = _make_link()
        assert len(link.token_hash) == 64
        assert all(c in '0123456789abcdef' for c in link.token_hash)

    def test_token_hash_matches_sha256(self):
        token, link = _make_link(token='known_token_value')
        assert link.token_hash == hash_token('known_token_value')

    def test_no_token_field_on_share_link(self):
        """ShareLink should not have a 'token' or 'plaintext_token' field."""
        _, link = _make_link()
        assert not hasattr(link, 'token')
        assert not hasattr(link, 'plaintext_token')
        assert not hasattr(link, 'plaintext')


# =====================================================================
# 2. Serialized representations
# =====================================================================


class TestSerializedRepresentations:
    """str/repr/dict conversions must not leak plaintext."""

    def test_str_does_not_contain_plaintext(self):
        token, link = _make_link(token='STR_LEAK_CHECK')
        assert 'STR_LEAK_CHECK' not in str(link)

    def test_repr_does_not_contain_plaintext(self):
        token, link = _make_link(token='REPR_LEAK_CHECK')
        assert 'REPR_LEAK_CHECK' not in repr(link)

    def test_dataclass_dict_does_not_contain_plaintext(self):
        token, link = _make_link(token='DICT_LEAK_CHECK')
        from dataclasses import asdict
        d = asdict(link)
        serialized = json.dumps(d, default=str)
        assert 'DICT_LEAK_CHECK' not in serialized


# =====================================================================
# 3. Repository internal storage
# =====================================================================


class TestRepositoryStorage:
    """Repository persists only hashes, never plaintext."""

    @pytest.mark.asyncio
    async def test_internal_dict_no_plaintext(self, repo):
        token, link = _make_link(token='REPO_INTERNAL_SECRET')
        await repo.create(link)

        for stored in repo._links.values():
            for attr in vars(stored):
                val = str(getattr(stored, attr))
                assert 'REPO_INTERNAL_SECRET' not in val

    @pytest.mark.asyncio
    async def test_bulk_create_no_plaintext(self, repo):
        tokens = []
        for i in range(10):
            token, link = _make_link(token=f'BULK_SECRET_{i}')
            tokens.append(token)
            await repo.create(link)

        all_stored = list(repo._links.values())
        for stored in all_stored:
            for t in tokens:
                assert t not in str(stored.token_hash)

    @pytest.mark.asyncio
    async def test_list_result_no_plaintext(self, repo):
        token, link = _make_link(token='LIST_SECRET_TOKEN')
        await repo.create(link)

        links = await repo.list_for_workspace('ws_1')
        for l in links:
            serialized = str(vars(l))
            assert 'LIST_SECRET_TOKEN' not in serialized

    @pytest.mark.asyncio
    async def test_get_by_hash_result_no_plaintext(self, repo):
        token, link = _make_link(token='HASH_LOOKUP_SECRET')
        await repo.create(link)

        found = await repo.get_by_token_hash(hash_token('HASH_LOOKUP_SECRET'))
        assert found is not None
        serialized = str(vars(found))
        assert 'HASH_LOOKUP_SECRET' not in serialized

    @pytest.mark.asyncio
    async def test_revoke_result_no_plaintext(self, repo):
        token, link = _make_link(token='REVOKE_SECRET')
        await repo.create(link)
        revoked = await repo.revoke(link.id, 'ws_1')
        assert revoked is not None
        serialized = str(vars(revoked))
        assert 'REVOKE_SECRET' not in serialized


# =====================================================================
# 4. Hash properties
# =====================================================================


class TestHashProperties:

    def test_hash_length_is_64(self):
        """SHA-256 hex digest is always 64 characters."""
        for _ in range(50):
            h = hash_token(generate_share_token())
            assert len(h) == 64

    def test_hash_is_lowercase_hex(self):
        for _ in range(50):
            h = hash_token(generate_share_token())
            assert all(c in '0123456789abcdef' for c in h)

    def test_distinct_tokens_distinct_hashes(self):
        """50 unique tokens should produce 50 unique hashes."""
        tokens = [generate_share_token() for _ in range(50)]
        hashes = {hash_token(t) for t in tokens}
        assert len(hashes) == 50

    def test_hash_deterministic(self):
        token = generate_share_token()
        assert hash_token(token) == hash_token(token)

    def test_token_not_substring_of_hash(self):
        """The plaintext token should not appear as substring of its hash."""
        for _ in range(20):
            token = generate_share_token()
            h = hash_token(token)
            assert token not in h


# =====================================================================
# 5. Token generation entropy
# =====================================================================


class TestTokenEntropy:

    def test_token_length_sufficient(self):
        """Generated tokens should have sufficient entropy (at least 32 bytes)."""
        assert TOKEN_BYTES >= 32

    def test_tokens_never_empty(self):
        for _ in range(100):
            assert len(generate_share_token()) > 0

    def test_tokens_url_safe(self):
        allowed = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=')
        for _ in range(50):
            token = generate_share_token()
            assert all(c in allowed for c in token)
