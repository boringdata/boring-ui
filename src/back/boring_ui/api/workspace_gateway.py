"""Workspace gateway boundary and mode dispatch.

This module centralizes local-vs-sandbox mode selection so route handlers
can depend on a stable app-level boundary instead of runtime env details.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .config import APIConfig, RuntimeConfig, SandboxConfig
from .exec_client import SpritesExecClient
from .exec_policy import ExecTemplateRegistry, create_default_registry as create_default_exec_registry
from .proxy_client import SpritesProxyClient
from .services_client import SpritesServicesClient
from .storage import Storage


@dataclass(frozen=True)
class SpritesGateway:
    """Composed sandbox clients behind a single boundary."""

    services: SpritesServicesClient
    proxy: SpritesProxyClient
    exec: SpritesExecClient


class WorkspaceGateway(ABC):
    """Application-level boundary for local vs sandbox behavior."""

    mode: str

    @property
    def is_local(self) -> bool:
        return self.mode == 'local'

    @property
    def is_sandbox(self) -> bool:
        return self.mode == 'sandbox'

    @abstractmethod
    async def check_ready(self) -> bool:
        """Return whether this gateway is ready to serve requests."""

    @abstractmethod
    def describe(self) -> dict:
        """Return non-sensitive diagnostic metadata for this gateway."""


class LocalWorkspaceGateway(WorkspaceGateway):
    """Local-mode gateway using in-process services."""

    def __init__(self, api_config: APIConfig, storage: Storage) -> None:
        self.mode = 'local'
        self.api_config = api_config
        self.storage = storage

    async def check_ready(self) -> bool:
        return True

    def describe(self) -> dict:
        return {
            'mode': self.mode,
            'workspace_root': str(self.api_config.workspace_root),
        }


class SandboxWorkspaceGateway(WorkspaceGateway):
    """Sandbox-mode gateway backed by Sprites clients."""

    def __init__(
        self,
        sandbox_config: SandboxConfig,
        sprites: SpritesGateway,
    ) -> None:
        self.mode = 'sandbox'
        self.sandbox_config = sandbox_config
        self.sprites = sprites

    async def check_ready(self) -> bool:
        return await self.sprites.services.is_ready()

    def describe(self) -> dict:
        return {
            'mode': self.mode,
            'sprite_name': self.sandbox_config.sprite_name,
            'service_target': {
                'host': self.sandbox_config.service_target.host,
                'port': self.sandbox_config.service_target.port,
                'path': self.sandbox_config.service_target.path,
            },
        }


def create_workspace_gateway(
    api_config: APIConfig,
    runtime_config: RuntimeConfig,
    storage: Storage,
    *,
    services_client: SpritesServicesClient | None = None,
    proxy_client: SpritesProxyClient | None = None,
    exec_client: SpritesExecClient | None = None,
    exec_registry: ExecTemplateRegistry | None = None,
) -> WorkspaceGateway:
    """Create the mode-dispatched workspace gateway."""
    if runtime_config.workspace_mode == 'local' or runtime_config.sandbox is None:
        return LocalWorkspaceGateway(api_config, storage)

    sandbox = runtime_config.sandbox
    services = services_client or SpritesServicesClient(sandbox)
    proxy = proxy_client or SpritesProxyClient(sandbox)
    registry = exec_registry or create_default_exec_registry()
    exec_gateway = exec_client or SpritesExecClient(sandbox, registry)

    return SandboxWorkspaceGateway(
        sandbox,
        SpritesGateway(
            services=services,
            proxy=proxy,
            exec=exec_gateway,
        ),
    )

