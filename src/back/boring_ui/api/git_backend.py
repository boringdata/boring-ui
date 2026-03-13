"""GitBackend ABC and domain types for pluggable git operations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypedDict


# ── Domain types ──────────────────────────────────────────────────────


class StatusEntry(TypedDict):
    """Single file status entry from git status."""
    path: str
    status: str   # M, A, D, U, C


class RemoteInfo(TypedDict):
    """Git remote entry."""
    remote: str
    url: str


@dataclass(frozen=True)
class GitCredentials:
    """Opaque credential object passed through to backend."""
    username: str
    password: str


# ── Error hierarchy ───────────────────────────────────────────────────


class GitBackendError(Exception):
    """Base error for all git backend failures."""


class GitCommandError(GitBackendError):
    """Git command execution failed."""

    def __init__(self, message: str, stderr: str = '', exit_code: int | None = None):
        super().__init__(message)
        self.stderr = stderr
        self.exit_code = exit_code


class GitNotRepoError(GitBackendError):
    """Workspace is not a git repository."""


class GitConflictError(GitBackendError):
    """Merge conflict."""


class GitAuthError(GitBackendError):
    """Authentication/credential failure."""


# ── ABC ───────────────────────────────────────────────────────────────


class GitBackend(ABC):
    """Pluggable git operations backend.

    Returns domain-level values, NOT HTTP-shaped dicts. The GitService
    adapter wraps results into API response dicts and maps errors to
    HTTPException.

    Error contract: backends raise GitBackendError subclasses for all
    failures. GitService catches only GitBackendError, never subprocess
    or other implementation-specific exceptions.

    Path contract: all path arguments are repo-relative strings, already
    validated by GitService. Backends must not re-validate.
    """

    # ── Repo state ──

    @abstractmethod
    def is_repo(self) -> bool:
        """Check if workspace is a git repository."""
        ...

    @abstractmethod
    def status(self) -> list[StatusEntry]:
        """Return list of changed files with status codes.

        Returns empty list if not a repo.
        """
        ...

    @abstractmethod
    def diff(self, path: str) -> str:
        """Return unified diff for a repo-relative path against HEAD.

        Returns empty string if file has no diff.
        """
        ...

    @abstractmethod
    def show(self, path: str) -> str | None:
        """Return file content at HEAD, or None if not tracked."""
        ...

    # ── Write operations ──

    @abstractmethod
    def init(self) -> None:
        """Initialize a git repository in the workspace."""
        ...

    @abstractmethod
    def add(self, paths: list[str] | None = None) -> None:
        """Stage files. If paths is None, stage all changes."""
        ...

    @abstractmethod
    def commit(self, message: str, author_name: str | None = None,
               author_email: str | None = None) -> str:
        """Create a commit. Returns the commit OID as a string.

        Raises GitCommandError if nothing to commit.
        """
        ...

    @abstractmethod
    def push(self, remote: str, branch: str | None = None,
             credentials: GitCredentials | None = None) -> None:
        """Push to a remote."""
        ...

    @abstractmethod
    def pull(self, remote: str, branch: str | None = None,
             credentials: GitCredentials | None = None) -> None:
        """Pull from a remote."""
        ...

    @abstractmethod
    def clone(self, url: str, branch: str | None = None,
              credentials: GitCredentials | None = None) -> None:
        """Clone a repository INTO the workspace root.

        Precondition: workspace_root exists. Backend is responsible for
        target directory semantics.
        """
        ...

    # ── Branches ──

    @abstractmethod
    def branches(self) -> tuple[list[str], str | None]:
        """List local branches.

        Returns (branch_names, current_branch_or_none).
        """
        ...

    @abstractmethod
    def current_branch_name(self) -> str | None:
        """Return the current branch name, or None if detached/not a repo."""
        ...

    @abstractmethod
    def create_branch(self, name: str, checkout: bool = True) -> None:
        """Create a new branch, optionally checking it out."""
        ...

    @abstractmethod
    def checkout(self, name: str) -> None:
        """Switch to an existing branch."""
        ...

    @abstractmethod
    def merge(self, source: str, message: str | None = None) -> None:
        """Merge source branch into current branch.

        Raises GitConflictError on merge conflict.
        """
        ...

    # ── Remotes ──

    @abstractmethod
    def add_remote(self, name: str, url: str) -> None:
        """Add or replace a remote."""
        ...

    @abstractmethod
    def remove_remote(self, name: str) -> None:
        """Remove a remote. Ignores if not found."""
        ...

    @abstractmethod
    def list_remotes(self) -> list[RemoteInfo]:
        """List configured remotes."""
        ...
