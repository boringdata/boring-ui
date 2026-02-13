"""Share-link domain model with token-hash persistence.

Bead: bd-223o.12.1 (F1)

Implements the share-link data model from Feature 3 design doc sections
12 (schema) and 18.6 (acceptance criteria):

  - Only token_hash is persisted; plaintext token is never stored.
  - Path access is exact-path scoped.
  - Expired links return 410; revoked/unknown links return 404.
  - Access modes: read, write.

Security invariant:
  The plaintext share token is generated once and returned to the creator.
  Only the SHA-256 hash is stored in the database.  Token validation
  requires hashing the presented token and comparing against stored hashes.

This module provides:
  1. ``ShareLink`` — domain object matching cloud.file_share_links schema.
  2. ``ShareLinkRepository`` — abstract storage protocol.
  3. ``InMemoryShareLinkRepository`` — test implementation.
  4. ``generate_share_token`` / ``hash_token`` — token lifecycle helpers.
  5. Domain exceptions: ShareLinkNotFound, ShareLinkExpired, ShareLinkRevoked.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

# ── Constants ─────────────────────────────────────────────────────────

TOKEN_BYTES = 32  # 256-bit tokens.
DEFAULT_EXPIRY_HOURS = 72  # 3-day default.


# ── Token operations ──────────────────────────────────────────────────


def generate_share_token() -> str:
    """Generate a cryptographically random URL-safe share token.

    The returned plaintext token is returned to the creator exactly once.
    Only the hash should be persisted.
    """
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(plaintext: str) -> str:
    """Compute the SHA-256 hash of a plaintext share token.

    This is the value stored in ``cloud.file_share_links.token_hash``.
    """
    return hashlib.sha256(plaintext.encode('utf-8')).hexdigest()


# ── Domain exceptions ─────────────────────────────────────────────────


class ShareLinkNotFound(Exception):
    """No share link matches the given token hash."""


class ShareLinkExpired(Exception):
    """Share link exists but has passed its expiry time."""

    def __init__(self, share_id: int, expired_at: datetime) -> None:
        self.share_id = share_id
        self.expired_at = expired_at
        super().__init__(f'Share link {share_id} expired at {expired_at}')


class ShareLinkRevoked(Exception):
    """Share link was explicitly revoked by an admin."""

    def __init__(self, share_id: int, revoked_at: datetime) -> None:
        self.share_id = share_id
        self.revoked_at = revoked_at
        super().__init__(f'Share link {share_id} revoked at {revoked_at}')


# ── Domain model ──────────────────────────────────────────────────────


@dataclass
class ShareLink:
    """Share link domain object matching cloud.file_share_links schema.

    Attributes:
        id: Auto-generated identity.
        workspace_id: Which workspace owns this link.
        path: Exact file path being shared (no traversal allowed).
        token_hash: SHA-256 hash of the plaintext token.
        access: Access mode — 'read' or 'write'.
        created_by: User ID who created the share.
        expires_at: When the link becomes invalid.
        revoked_at: When the link was revoked (None if active).
        created_at: Creation timestamp.
    """

    id: int
    workspace_id: str
    path: str
    token_hash: str
    access: str  # 'read' | 'write'
    created_by: str
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_active(self) -> bool:
        return not self.is_expired and not self.is_revoked


# ── Repository protocol ──────────────────────────────────────────────


class ShareLinkRepository(Protocol):
    """Abstract share link storage.

    Implementations: InMemoryShareLinkRepository (testing),
    SupabaseShareLinkRepository (production).
    """

    async def create(self, link: ShareLink) -> ShareLink: ...

    async def get_by_token_hash(self, token_hash: str) -> ShareLink | None: ...

    async def list_for_workspace(
        self, workspace_id: str, *, include_revoked: bool = False,
    ) -> list[ShareLink]: ...

    async def revoke(
        self, share_id: int, workspace_id: str,
    ) -> ShareLink | None: ...

    async def resolve_token(self, plaintext_token: str) -> ShareLink:
        """Resolve a plaintext token to an active share link.

        Raises:
            ShareLinkNotFound: No link matches the token hash.
            ShareLinkExpired: Link exists but is past expiry.
            ShareLinkRevoked: Link exists but was revoked.
        """
        ...


# ── In-memory implementation ─────────────────────────────────────────


class InMemoryShareLinkRepository:
    """Simple in-memory share link store for testing."""

    def __init__(self) -> None:
        self._links: dict[int, ShareLink] = {}
        self._next_id: int = 1

    async def create(self, link: ShareLink) -> ShareLink:
        link.id = self._next_id
        self._next_id += 1
        self._links[link.id] = link
        return link

    async def get_by_token_hash(self, token_hash: str) -> ShareLink | None:
        for link in self._links.values():
            if link.token_hash == token_hash:
                return link
        return None

    async def list_for_workspace(
        self,
        workspace_id: str,
        *,
        include_revoked: bool = False,
    ) -> list[ShareLink]:
        result = []
        for link in self._links.values():
            if link.workspace_id != workspace_id:
                continue
            if not include_revoked and link.is_revoked:
                continue
            result.append(link)
        return sorted(result, key=lambda l: l.created_at)

    async def revoke(
        self, share_id: int, workspace_id: str,
    ) -> ShareLink | None:
        link = self._links.get(share_id)
        if link is None or link.workspace_id != workspace_id:
            return None
        if link.revoked_at is None:
            link.revoked_at = datetime.now(timezone.utc)
        return link

    async def resolve_token(self, plaintext_token: str) -> ShareLink:
        """Resolve plaintext token → active share link.

        Raises ShareLinkNotFound, ShareLinkExpired, or ShareLinkRevoked.
        """
        token_h = hash_token(plaintext_token)
        link = await self.get_by_token_hash(token_h)

        if link is None:
            raise ShareLinkNotFound()

        if link.is_revoked:
            raise ShareLinkRevoked(link.id, link.revoked_at)

        if link.is_expired:
            raise ShareLinkExpired(link.id, link.expires_at)

        return link
