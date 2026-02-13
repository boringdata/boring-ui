"""Supabase-backed ShareRepository implementation.

Bead: bd-1joj.7 (DB4)

Implements the ShareRepository protocol using the SupabaseClient (DB0)
to persist share links in cloud.file_share_links via PostgREST.

Security invariants:
  - Plaintext token is NEVER stored; only SHA-256 hash persisted
  - Path traversal (../) rejected at creation time
  - access constrained to read/write
"""

from __future__ import annotations

import hashlib
import posixpath
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any

from .supabase_client import SupabaseClient

_VALID_ACCESS = frozenset({"read", "write"})
_DEFAULT_EXPIRY_HOURS = 24


def _hash_token(token: str) -> str:
    """SHA-256 hash a plaintext token."""
    return hashlib.sha256(token.encode()).hexdigest()


def _normalize_path(path: str) -> str:
    """Normalize to absolute workspace-relative path, reject traversal."""
    # Reject obvious traversal
    if ".." in path:
        raise ValueError("Path traversal not allowed")
    # Normalize and ensure absolute (workspace-relative)
    normalized = posixpath.normpath(path)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


class SupabaseShareLinkRepository:
    """ShareRepository backed by cloud.file_share_links via PostgREST."""

    TABLE = "cloud.file_share_links"

    def __init__(self, client: SupabaseClient) -> None:
        self._client = client

    async def create_share(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a share link. Returns dict with 'token' (plaintext, one-time)."""
        path = data.get("path", "")
        normalized_path = _normalize_path(path)

        access = data.get("access", "read")
        if access not in _VALID_ACCESS:
            raise ValueError(f"access must be one of {_VALID_ACCESS}, got {access!r}")

        expiry_hours = data.get("expires_in_hours", _DEFAULT_EXPIRY_HOURS)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        ).isoformat()

        # Generate token; persist only hash
        plaintext_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(plaintext_token)

        row = {
            "workspace_id": data["workspace_id"],
            "token_hash": token_hash,
            "path": normalized_path,
            "access": access,
            "created_by": data["created_by"],
            "expires_at": expires_at,
        }
        rows = await self._client.insert(self.TABLE, row)
        result = rows[0]
        # Return plaintext token exactly once (not stored in DB)
        result["token"] = plaintext_token
        return result

    async def get_share(self, token: str) -> dict[str, Any] | None:
        """Look up a share link by plaintext token (hashed for DB lookup).

        Returns the share dict if found (caller checks expires_at/revoked_at),
        or None if the hash doesn't match any row.
        """
        token_hash = _hash_token(token)
        rows = await self._client.select(
            self.TABLE,
            filters={"token_hash": ("eq", token_hash)},
            limit=1,
        )
        return rows[0] if rows else None

    async def delete_share(self, share_id: str) -> bool:
        """Soft-revoke a share link by setting revoked_at."""
        now = datetime.now(timezone.utc).isoformat()
        rows = await self._client.update(
            self.TABLE,
            filters={"id": ("eq", share_id)},
            data={"revoked_at": now},
        )
        return len(rows) > 0

    async def list_shares(self, workspace_id: str) -> list[dict[str, Any]]:
        """List all share links for a workspace (including expired/revoked)."""
        return await self._client.select(
            self.TABLE,
            filters={"workspace_id": ("eq", workspace_id)},
            order="created_at.desc",
        )
