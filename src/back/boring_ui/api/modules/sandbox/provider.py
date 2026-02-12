"""Abstract interface for sandbox providers.

Providers manage sandbox-agent instances running in different environments:
- LocalProvider: subprocess on host machine
- SpritesProvider: remote sandbox on Sprites.dev
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncIterator, Generic, TypeVar

from .sanitize import sanitize_branch, sanitize_repo_url


# ---------------------------------------------------------------------------
# SandboxStatus  (bd-1ni.2.1)
# ---------------------------------------------------------------------------

class SandboxStatus(str, Enum):
    """Sandbox lifecycle states.

    Covers both local (creating → running → stopped) and Sprites
    (creating → running → sleeping → waking → running) lifecycles.
    """

    creating = "creating"
    starting = "starting"
    running = "running"
    sleeping = "sleeping"
    waking = "waking"
    stopping = "stopping"
    stopped = "stopped"
    error = "error"


# ---------------------------------------------------------------------------
# SandboxCreateConfig  (bd-1ni.2.1)
# ---------------------------------------------------------------------------

@dataclass
class SandboxCreateConfig:
    """Typed configuration for sandbox creation.

    Validates and sanitizes user-controlled inputs on construction.
    Credentials are never logged.
    """

    user_id: str = ""
    repo_url: str = ""
    branch: str = "main"
    agent: str = "claude"

    # Credentials — mutually exclusive for Sprites; both optional for Local
    anthropic_api_key: str = ""
    oauth_token: str = ""

    # Timeouts (seconds)
    setup_timeout: float = 300.0
    health_timeout: float = 30.0

    # Direct-connect internals (set by manager, not user)
    service_auth_secret: str = ""
    cors_origin: str = ""

    def __post_init__(self) -> None:
        if self.repo_url:
            self.repo_url = sanitize_repo_url(self.repo_url)
        if self.branch:
            self.branch = sanitize_branch(self.branch)

    def validate_credentials(self, require: bool = False) -> None:
        """Check credential invariants.

        Args:
            require: If True, at least one credential must be set.

        Raises:
            ValueError: On invalid credential combination.
        """
        has_key = bool(self.anthropic_api_key)
        has_oauth = bool(self.oauth_token)

        if has_key and has_oauth:
            raise ValueError(
                "Provide either anthropic_api_key or oauth_token, not both"
            )
        if require and not has_key and not has_oauth:
            raise ValueError(
                "At least one credential (anthropic_api_key or oauth_token) is required"
            )


# ---------------------------------------------------------------------------
# SandboxInfo
# ---------------------------------------------------------------------------

@dataclass
class SandboxInfo:
    """Information about a sandbox instance."""

    id: str
    base_url: str  # URL to reach sandbox-agent API
    status: str  # starting, running, stopped, error
    workspace_path: str  # Path to workspace inside sandbox
    provider: str  # "local" or "sprites"

    # Extensions for Sprites + Direct Connect (all have defaults for compat)
    protocol: str = "rest+sse"  # e.g. "rest+sse" for sandbox-agent
    user_id: str = ""  # optional; may be empty in single-user
    repo_url: str = ""  # optional; for idempotency checks / UI display


# ---------------------------------------------------------------------------
# Checkpoint types  (bd-1ni.2.2)
# ---------------------------------------------------------------------------

T = TypeVar("T")


@dataclass
class CheckpointInfo:
    """Metadata for a single checkpoint."""

    id: str
    label: str = ""
    created_at: datetime | None = None
    size_bytes: int | None = None


@dataclass
class CheckpointResult(Generic[T]):
    """Structured result for checkpoint operations.

    Allows callers to handle 'not supported' cleanly without try/except.
    """

    success: bool
    data: T | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# SandboxProvider
# ---------------------------------------------------------------------------

class SandboxProvider(ABC):
    """Abstract interface for sandbox providers.

    Implementations must handle the lifecycle of sandbox-agent instances:
    - Creating/starting a sandbox with sandbox-agent running
    - Destroying/stopping the sandbox
    - Health checking
    - Log collection

    Optional capabilities (override to enable):
    - Checkpoints (create/restore/list)
    - Credential updates
    """

    @abstractmethod
    async def create(self, sandbox_id: str, config: dict) -> SandboxInfo:
        """Create and start a sandbox with sandbox-agent running.

        Args:
            sandbox_id: Unique identifier for this sandbox
            config: Provider-specific configuration

        Returns:
            SandboxInfo with connection details
        """
        pass

    @abstractmethod
    async def destroy(self, sandbox_id: str) -> None:
        """Stop and cleanup sandbox.

        Args:
            sandbox_id: The sandbox to destroy
        """
        pass

    @abstractmethod
    async def get_info(self, sandbox_id: str) -> SandboxInfo | None:
        """Get sandbox status and URL.

        Args:
            sandbox_id: The sandbox to query

        Returns:
            SandboxInfo if sandbox exists, None otherwise
        """
        pass

    @abstractmethod
    async def get_logs(self, sandbox_id: str, limit: int = 100) -> list[str]:
        """Get sandbox-agent logs.

        Args:
            sandbox_id: The sandbox to get logs from
            limit: Maximum number of log lines to return

        Returns:
            List of log lines (most recent last)
        """
        pass

    @abstractmethod
    async def stream_logs(self, sandbox_id: str) -> AsyncIterator[str]:
        """Async generator yielding log lines.

        Args:
            sandbox_id: The sandbox to stream logs from

        Yields:
            Log lines as they become available
        """
        pass

    @abstractmethod
    async def health_check(self, sandbox_id: str) -> bool:
        """Check if sandbox-agent is responding.

        Args:
            sandbox_id: The sandbox to check

        Returns:
            True if sandbox-agent is healthy
        """
        pass

    # ------ Checkpoints (bd-1ni.2.2) ------

    def supports_checkpoints(self) -> bool:
        """Whether this provider supports checkpoint operations."""
        return False

    async def create_checkpoint(
        self,
        sandbox_id: str,
        label: str = "",
    ) -> CheckpointResult[CheckpointInfo]:
        """Create a checkpoint of the sandbox state.

        SECURITY: Checkpoints may capture workspace files but must NOT
        include credential files. Implementations must exclude secrets.
        """
        return CheckpointResult(success=False, error="Not supported")

    async def restore_checkpoint(
        self,
        sandbox_id: str,
        checkpoint_id: str,
    ) -> CheckpointResult[None]:
        """Restore sandbox to a checkpoint.

        After restore, credentials may be stale — call
        ``update_credentials`` to refresh them.
        """
        return CheckpointResult(success=False, error="Not supported")

    async def list_checkpoints(
        self,
        sandbox_id: str,
    ) -> CheckpointResult[list[CheckpointInfo]]:
        """List available checkpoints for a sandbox."""
        return CheckpointResult(success=False, error="Not supported")

    # ------ Credential update (bd-1ni.2.3) ------

    async def update_credentials(
        self,
        sandbox_id: str,
        anthropic_api_key: str | None = None,
        oauth_token: str | None = None,
    ) -> bool:
        """Update credentials in an existing sandbox.

        Useful for credential rotation, post-checkpoint-restore refresh,
        or suspected compromise. At least one credential should be
        provided; passing neither returns False.

        SECURITY: Implementations must shell-escape values to prevent
        injection and must never log credential values.

        Returns:
            True if credentials were updated. False if the provider
            does not support credential updates (e.g. LocalProvider).
        """
        return False
