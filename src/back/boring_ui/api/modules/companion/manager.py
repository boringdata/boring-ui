"""Companion manager for orchestrating server lifecycle.

Provides a simplified interface over CompanionProvider,
handling the default instance and service token storage.
"""
from pathlib import Path
from typing import AsyncIterator

from .provider import CompanionProvider, CompanionInfo


class CompanionManager:
    """Manages Companion server lifecycle.

    Example:
        provider = CompanionProvider(port=3456)
        manager = CompanionManager(provider, service_token="abc123")
        url = await manager.get_base_url()  # Starts server if needed
        await manager.shutdown()
    """

    def __init__(
        self,
        provider: CompanionProvider,
        service_token: str | None = None,
    ):
        self.provider = provider
        self.service_token = service_token
        self.default_instance_id = "default"

    async def ensure_running(self) -> CompanionInfo:
        """Get or create the default Companion instance."""
        info = await self.provider.get_info(self.default_instance_id)
        if info and info.status == "running":
            return info
        return await self.provider.create(self.default_instance_id, {})

    async def get_base_url(self) -> str:
        """Get the base URL for the running Companion.

        Starts the server if not already running.
        """
        info = await self.ensure_running()
        return info.base_url

    async def get_info(self) -> CompanionInfo | None:
        """Get current info without starting."""
        return await self.provider.get_info(self.default_instance_id)

    async def get_logs(self, limit: int = 100) -> list[str]:
        return await self.provider.get_logs(self.default_instance_id, limit)

    async def stream_logs(self) -> AsyncIterator[str]:
        async for line in self.provider.stream_logs(self.default_instance_id):
            yield line

    async def health_check(self) -> bool:
        return await self.provider.health_check(self.default_instance_id)

    async def shutdown(self) -> None:
        """Stop and cleanup the Companion server."""
        await self.provider.destroy(self.default_instance_id)


def create_companion_provider(config: dict) -> CompanionProvider:
    """Factory to create CompanionProvider from config dict.

    Args:
        config: Configuration with:
            - COMPANION_PORT: Port (default: 3456)
            - COMPANION_WORKSPACE: Workspace path
            - COMPANION_SIGNING_KEY: Hex signing key for JWT auth
            - COMPANION_CORS_ORIGIN: CORS allowed origin
            - COMPANION_SERVER_DIR: Path to server source
            - COMPANION_EXTERNAL_HOST: External hostname/IP for browser access
            - COMPANION_RUN_MODE: 'local' or 'hosted' (default: 'local')
    """
    return CompanionProvider(
        port=int(config.get("COMPANION_PORT", 3456)),
        workspace=Path(config.get("COMPANION_WORKSPACE", ".")),
        signing_key_hex=config.get("COMPANION_SIGNING_KEY"),
        cors_origin=config.get("COMPANION_CORS_ORIGIN"),
        server_dir=Path(config["COMPANION_SERVER_DIR"]) if config.get("COMPANION_SERVER_DIR") else None,
        external_host=config.get("COMPANION_EXTERNAL_HOST"),
        run_mode=config.get("COMPANION_RUN_MODE", "local"),
    )
