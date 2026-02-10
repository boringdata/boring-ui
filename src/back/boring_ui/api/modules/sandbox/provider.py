"""Abstract interface for sandbox providers.

Providers manage sandbox-agent instances running in different environments:
- LocalProvider: subprocess on host machine
- ModalProvider: remote sandbox on Modal (future)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class SandboxInfo:
    """Information about a sandbox instance."""

    id: str
    base_url: str  # URL to reach sandbox-agent API
    status: str  # starting, running, stopped, error
    workspace_path: str  # Path to workspace inside sandbox
    provider: str  # "local" or "modal"


class SandboxProvider(ABC):
    """Abstract interface for sandbox providers.

    Implementations must handle the lifecycle of sandbox-agent instances:
    - Creating/starting a sandbox with sandbox-agent running
    - Destroying/stopping the sandbox
    - Health checking
    - Log collection
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
