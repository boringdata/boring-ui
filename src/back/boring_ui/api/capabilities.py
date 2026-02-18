"""Capabilities discovery and router registry for boring-ui API.

This module provides:
- A registry for tracking available routers/features
- A capabilities endpoint for UI feature discovery
"""
from dataclasses import dataclass, field
from typing import Callable, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .workspace_plugins import WorkspacePluginManager
from fastapi import APIRouter


@dataclass
class RouterInfo:
    """Metadata about a registered router."""
    name: str
    prefix: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    # Describes which logical service owns the route family in the service-split
    # architecture (may differ from the monolith process that currently mounts it).
    owner_service: str = ""
    # Canonical (contract) route families for this router. These are NOT used for
    # mounting; `prefix` + the router's internal paths are the implementation.
    canonical_families: list[str] = field(default_factory=list)


class RouterRegistry:
    """Registry for tracking available API routers.

    This allows dynamic router composition and capability discovery.

    Example:
        registry = RouterRegistry()
        registry.register('files', '/api/v1/files', create_file_router,
                         description='File operations')
        registry.register('git', '/api/v1/git', create_git_router,
                         description='Git operations')

        # Get all registered routers
        for info, factory in registry.all():
            app.include_router(factory(config), prefix=info.prefix)
    """

    def __init__(self):
        self._routers: dict[str, tuple[RouterInfo, Callable[..., APIRouter]]] = {}

    def register(
        self,
        name: str,
        prefix: str,
        factory: Callable[..., APIRouter],
        description: str = "",
        tags: list[str] | None = None,
        required_capabilities: list[str] | None = None,
        owner_service: str = "",
        canonical_families: list[str] | None = None,
    ) -> None:
        """Register a router factory.

        Args:
            name: Unique identifier for this router
            prefix: URL prefix (e.g., '/api/v1/git')
            factory: Function that creates the router
            description: Human-readable description
            tags: OpenAPI tags for grouping
            required_capabilities: Capabilities this router requires
        """

        def _normalize_str_list(value: list[str] | str | None) -> list[str]:
            # Defensive: prevent accidental `list("foo") -> ["f","o","o"]`.
            if value is None:
                return []
            if isinstance(value, str):
                return [value]
            return list(value)

        info = RouterInfo(
            name=name,
            prefix=prefix,
            description=description,
            tags=_normalize_str_list(tags),
            required_capabilities=_normalize_str_list(required_capabilities),
            owner_service=owner_service,
            canonical_families=_normalize_str_list(canonical_families),
        )
        self._routers[name] = (info, factory)

    def get(self, name: str) -> tuple[RouterInfo, Callable[..., APIRouter]] | None:
        """Get a router by name."""
        return self._routers.get(name)

    def list_names(self) -> list[str]:
        """List all registered router names."""
        return list(self._routers.keys())

    def all(self) -> list[tuple[RouterInfo, Callable[..., APIRouter]]]:
        """Get all registered routers."""
        return list(self._routers.values())

    def get_info(self, name: str) -> RouterInfo | None:
        """Get router info without the factory."""
        entry = self._routers.get(name)
        return entry[0] if entry else None


def create_default_registry() -> RouterRegistry:
    """Create a registry with the default boring-ui routers.

    This represents the standard router set for a boring-ui application.
    """
    from .modules.files import create_file_router
    from .modules.git import create_git_router
    from .modules.pty import create_pty_router
    from .modules.stream import create_stream_router
    from .approval import create_approval_router

    registry = RouterRegistry()

    # Core routers (always included in default setup)
    registry.register(
        'files',
        '/api/v1/files',
        create_file_router,
        description='File system operations (read, write, rename, delete)',
        tags=['files'],
        owner_service='workspace-core',
        canonical_families=['/api/v1/files/*'],
    )
    registry.register(
        'git',
        '/api/v1/git',
        create_git_router,
        description='Git operations (status, diff, show)',
        tags=['git'],
        owner_service='workspace-core',
        canonical_families=['/api/v1/git/*'],
    )

    # Optional routers
    registry.register(
        'pty',
        '/ws',
        create_pty_router,
        description='PTY WebSocket for shell terminals',
        tags=['websocket', 'terminal'],
        owner_service='pty-service',
        canonical_families=['/ws/pty', '/api/v1/pty/*'],
    )
    registry.register(
        'chat_claude_code',
        '/ws',
        create_stream_router,
        description='Claude stream WebSocket for AI chat',
        tags=['websocket', 'ai'],
        owner_service='agent-normal',
        canonical_families=['/ws/agent/normal/*', '/api/v1/agent/normal/*'],
    )
    # Backward compatibility alias: 'stream' -> 'chat_claude_code'
    registry.register(
        'stream',
        '/ws',
        create_stream_router,
        description='Claude stream WebSocket for AI chat (alias for chat_claude_code)',
        tags=['websocket', 'ai'],
        owner_service='agent-normal',
        canonical_families=['/ws/agent/normal/*', '/api/v1/agent/normal/*'],
    )
    registry.register(
        'approval',
        '/api',
        create_approval_router,
        description='Approval workflow endpoints',
        tags=['approval'],
        owner_service='boring-ui',
        canonical_families=['/api/approval/*'],
    )

    return registry


def create_capabilities_router(
    enabled_features: dict[str, bool],
    registry: RouterRegistry | None = None,
    config: "APIConfig | None" = None,
    plugin_manager: "Any | None" = None,
) -> APIRouter:
    """Create a router for the capabilities endpoint.

    Args:
        enabled_features: Map of feature name -> enabled status
        registry: Optional router registry for detailed info
        config: Optional APIConfig (includes optional contract-metadata exposure)

    Returns:
        Router with /capabilities endpoint
    """
    router = APIRouter(tags=['capabilities'])

    @router.get('/capabilities')
    async def get_capabilities():
        """Get API capabilities and available features.

        Returns a stable JSON structure describing what features
        are enabled in this API instance. The UI uses this to
        conditionally render components.
        """
        capabilities = {
            'version': '0.1.0',
            'features': enabled_features,
        }

        # Add router details if registry provided
        if registry:
            include_contract_metadata = bool(
                config and getattr(config, "capabilities_include_contract_metadata", False)
            )
            capabilities['routers'] = [
                {
                    'name': info.name,
                    'prefix': info.prefix,
                    'description': info.description,
                    'tags': info.tags,
                    'enabled': enabled_features.get(info.name, False),
                    # Keep schema stable: contract metadata is always present, but
                    # null unless explicitly enabled.
                    'contract_metadata': (
                        {
                            'owner_service': info.owner_service or None,
                            'canonical_families': info.canonical_families,
                        }
                        if include_contract_metadata
                        else None
                    ),
                }
                for info, _ in registry.all()
            ]

        # Workspace plugin panes
        if plugin_manager is not None:
            capabilities['workspace_panes'] = plugin_manager.list_workspace_panes()
            capabilities['workspace_routes'] = plugin_manager.list_workspace_routes()

        # Service connection info for direct-connect panels
        if config and config.companion_url:
            services = capabilities.setdefault('services', {})
            services['companion'] = {
                'url': config.companion_url,
            }
        if config and config.pi_url:
            services = capabilities.setdefault('services', {})
            services['pi'] = {
                'url': config.pi_url,
                'mode': config.pi_mode,
            }

        return capabilities

    return router
