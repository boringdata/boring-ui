"""Sandbox manager for orchestrating sandbox lifecycle.

The manager provides a simplified interface over providers,
handling the default sandbox and provider selection.
"""
from pathlib import Path
from typing import AsyncIterator

from .provider import SandboxInfo, SandboxProvider
from .providers.local import LocalProvider


class SandboxManager:
    """Manages sandbox lifecycle using configured provider.

    Provides a high-level interface for:
    - Ensuring a sandbox is running (lazy creation)
    - Getting the base URL for proxying
    - Log access and streaming
    - Graceful shutdown

    Example:
        manager = SandboxManager(LocalProvider(port=2468))
        url = await manager.get_base_url()  # Starts sandbox if needed
        # Proxy requests to url
        await manager.shutdown()  # Cleanup
    """

    def __init__(self, provider: SandboxProvider, service_token: str | None = None):
        """Initialize the manager.

        Args:
            provider: The sandbox provider to use
            service_token: Bearer token the sandbox-agent was started with.
                Used by proxy to authenticate forwarded requests.
        """
        self.provider = provider
        self.service_token = service_token
        self.default_sandbox_id = "default"

    async def ensure_running(self) -> SandboxInfo:
        """Get or create the default sandbox.

        Returns:
            SandboxInfo with connection details

        Raises:
            TimeoutError: If sandbox fails to start
        """
        info = await self.provider.get_info(self.default_sandbox_id)
        if info and info.status == "running":
            return info
        return await self.provider.create(self.default_sandbox_id, {})

    async def get_base_url(self) -> str:
        """Get the base URL for the running sandbox.

        Starts the sandbox if not already running.

        Returns:
            Base URL for sandbox-agent API
        """
        info = await self.ensure_running()
        return info.base_url

    async def get_info(self) -> SandboxInfo | None:
        """Get current sandbox info without starting it.

        Returns:
            SandboxInfo if sandbox exists, None otherwise
        """
        return await self.provider.get_info(self.default_sandbox_id)

    async def get_logs(self, limit: int = 100) -> list[str]:
        """Get sandbox logs.

        Args:
            limit: Maximum number of log lines

        Returns:
            List of log lines
        """
        return await self.provider.get_logs(self.default_sandbox_id, limit)

    async def stream_logs(self) -> AsyncIterator[str]:
        """Stream sandbox logs.

        Yields:
            Log lines as they arrive
        """
        async for line in self.provider.stream_logs(self.default_sandbox_id):
            yield line

    async def health_check(self) -> bool:
        """Check if sandbox is healthy.

        Returns:
            True if sandbox is running and responding
        """
        return await self.provider.health_check(self.default_sandbox_id)

    async def shutdown(self) -> None:
        """Stop and cleanup the sandbox."""
        await self.provider.destroy(self.default_sandbox_id)


def create_provider(config: dict) -> SandboxProvider:
    """Factory to create provider based on config.

    Args:
        config: Configuration dict with:
            - SANDBOX_PROVIDER: "local", "sprites", or "modal" (default: "local")
            - SANDBOX_PORT: Port for sandbox-agent (default: 2468)
            - SANDBOX_WORKSPACE: Workspace path for local (default: ".")
            - SANDBOX_TOKEN: Bearer token for auth (optional, local)
            - SANDBOX_CORS_ORIGIN: CORS allowed origin (optional, local)
            - SPRITES_TOKEN: Sprites.dev API token (required for sprites)
            - SPRITES_ORG: Sprites.dev org slug (required for sprites)
            - SPRITES_NAME_PREFIX: Sprite name prefix (optional, sprites)

    Returns:
        Configured SandboxProvider instance

    Raises:
        ValueError: If unknown provider type or missing required config
    """
    provider_type = config.get("SANDBOX_PROVIDER", "local")

    if provider_type == "local":
        return LocalProvider(
            port=int(config.get("SANDBOX_PORT", 2468)),
            workspace=Path(config.get("SANDBOX_WORKSPACE", ".")),
            token=config.get("SANDBOX_TOKEN"),
            cors_origin=config.get("SANDBOX_CORS_ORIGIN"),
        )
    elif provider_type == "sprites":
        from .providers.sprites import SpritesProvider

        token = config.get("SPRITES_TOKEN", "")
        if not token:
            raise ValueError(
                "SPRITES_TOKEN is required when SANDBOX_PROVIDER=sprites. "
                "Set it in your environment or config."
            )
        org = config.get("SPRITES_ORG", "")
        if not org:
            raise ValueError(
                "SPRITES_ORG is required when SANDBOX_PROVIDER=sprites."
            )
        return SpritesProvider(
            token=token,
            org=org,
            name_prefix=config.get("SPRITES_NAME_PREFIX", ""),
            sandbox_agent_port=int(config.get("SANDBOX_PORT", 2468)),
        )
    elif provider_type == "modal":
        from .providers.modal import ModalProvider

        return ModalProvider()
    else:
        raise ValueError(f"Unknown sandbox provider: {provider_type}")
