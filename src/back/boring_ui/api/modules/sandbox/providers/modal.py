"""Modal sandbox provider (stub for future implementation).

This will run sandbox-agent in an isolated Modal sandbox with:
- Ephemeral tmp filesystem as /workspace
- Auto-cleanup on timeout
- Public URL for API access
"""
from typing import AsyncIterator

from ..provider import SandboxInfo, SandboxProvider


class ModalProvider(SandboxProvider):
    """Runs sandbox-agent in Modal sandbox with isolated tmp filesystem.

    Future implementation will:
    - Create Modal sandbox with sandbox-agent pre-installed
    - Mount ephemeral tmp filesystem as /workspace
    - Start sandbox-agent server inside container
    - Return public URL to sandbox-agent
    - Auto-cleanup on timeout

    This is a stub - not yet implemented.
    """

    async def create(self, sandbox_id: str, config: dict) -> SandboxInfo:
        """Create a Modal sandbox."""
        raise NotImplementedError(
            "Modal provider not yet implemented. Use 'local' provider."
        )

    async def destroy(self, sandbox_id: str) -> None:
        """Destroy a Modal sandbox."""
        raise NotImplementedError("Modal provider not yet implemented.")

    async def get_info(self, sandbox_id: str) -> SandboxInfo | None:
        """Get Modal sandbox info."""
        raise NotImplementedError("Modal provider not yet implemented.")

    async def get_logs(self, sandbox_id: str, limit: int = 100) -> list[str]:
        """Get Modal sandbox logs."""
        raise NotImplementedError("Modal provider not yet implemented.")

    async def stream_logs(self, sandbox_id: str) -> AsyncIterator[str]:
        """Stream Modal sandbox logs."""
        raise NotImplementedError("Modal provider not yet implemented.")
        # Required for type checking - unreachable
        yield ""  # pragma: no cover

    async def health_check(self, sandbox_id: str) -> bool:
        """Check Modal sandbox health."""
        raise NotImplementedError("Modal provider not yet implemented.")
