"""Supabase client error hierarchy.

Bead: bd-1joj.3 (DB0)

We intentionally keep these errors small and dependency-free so they can be used
across repositories without leaking httpx.Response objects (or secrets).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SupabaseError(Exception):
    """Base Supabase error for PostgREST requests."""

    status_code: int
    message: str
    code: str | None = None
    details: str | None = None
    hint: str | None = None

    def __str__(self) -> str:  # pragma: no cover (covered via subclass tests)
        bits: list[str] = [f"SupabaseError(status={self.status_code})", self.message]
        if self.code:
            bits.append(f"code={self.code}")
        if self.details:
            bits.append(f"details={self.details}")
        return " ".join(bits)


class SupabaseAuthError(SupabaseError):
    """401/403 auth errors (bad key, RLS, expired session, etc.)."""


class SupabaseNotFoundError(SupabaseError):
    """404 errors (missing table/view/route)."""


class SupabaseConflictError(SupabaseError):
    """409 conflicts (unique violations, etc.)."""

