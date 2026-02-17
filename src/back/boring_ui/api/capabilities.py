"""Capabilities discovery and router registry for boring-ui API.

This module provides:
- A registry for tracking available routers/features
- A capabilities endpoint for UI feature discovery
"""
from dataclasses import dataclass, field
from typing import Callable, Any
from fastapi import APIRouter


@dataclass
class RouterInfo:
    """Metadata about a registered router."""
    name: str
    prefix: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)


class RouterRegistry:
    """Registry for tracking available API routers.

    This allows dynamic router composition and capability discovery.

    Example:
        registry = RouterRegistry()
        registry.register('files', '/api', create_file_router,
                         description='File operations')
        registry.register('git', '/api/git', create_git_router,
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
    ) -> None:
        """Register a router factory.

        Args:
            name: Unique identifier for this router
            prefix: URL prefix (e.g., '/api/git')
            factory: Function that creates the router
            description: Human-readable description
            tags: OpenAPI tags for grouping
            required_capabilities: Capabilities this router requires
        """
        info = RouterInfo(
            name=name,
            prefix=prefix,
            description=description,
            tags=tags or [],
            required_capabilities=required_capabilities or [],
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
        '/api',
        create_file_router,
        description='File system operations (read, write, rename, delete)',
        tags=['files'],
    )
    registry.register(
        'git',
        '/api/git',
        create_git_router,
        description='Git operations (status, diff, show)',
        tags=['git'],
    )

    # Optional routers
    registry.register(
        'pty',
        '/ws',
        create_pty_router,
        description='PTY WebSocket for shell terminals',
        tags=['websocket', 'terminal'],
    )
    registry.register(
        'chat_claude_code',
        '/ws',
        create_stream_router,
        description='Claude stream WebSocket for AI chat',
        tags=['websocket', 'ai'],
    )
    # Backward compatibility alias: 'stream' -> 'chat_claude_code'
    registry.register(
        'stream',
        '/ws',
        create_stream_router,
        description='Claude stream WebSocket for AI chat (alias for chat_claude_code)',
        tags=['websocket', 'ai'],
    )
    registry.register(
        'approval',
        '/api',
        create_approval_router,
        description='Approval workflow endpoints',
        tags=['approval'],
    )

    return registry


def create_capabilities_router(
    enabled_features: dict[str, bool],
    registry: RouterRegistry | None = None,
    config: "APIConfig | None" = None,
) -> APIRouter:
    """Create a router for the capabilities endpoint.

    Args:
        enabled_features: Map of feature name -> enabled status
        registry: Optional router registry for detailed info
        config: Optional APIConfig for services metadata

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
            capabilities['routers'] = [
                {
                    'name': info.name,
                    'prefix': info.prefix,
                    'description': info.description,
                    'tags': info.tags,
                    'enabled': enabled_features.get(info.name, False),
                }
                for info, _ in registry.all()
            ]

        # Service connection info for direct-connect panels
        if config and config.companion_url:
            services = capabilities.setdefault('services', {})
            services['companion'] = {
                'url': config.companion_url,
            }

        return capabilities

    return router
