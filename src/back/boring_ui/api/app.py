"""Application factory for boring-ui API."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APIConfig
from .storage import Storage, LocalStorage
from .modules.files import create_file_router
from .git_routes import create_git_router
from .pty_bridge import create_pty_router
from .stream_bridge import create_stream_router
from .approval import ApprovalStore, InMemoryApprovalStore, create_approval_router
from .capabilities import (
    RouterRegistry,
    create_default_registry,
    create_capabilities_router,
)


def create_app(
    config: APIConfig | None = None,
    storage: Storage | None = None,
    approval_store: ApprovalStore | None = None,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
    routers: list[str] | None = None,
    registry: RouterRegistry | None = None,
) -> FastAPI:
    """Create a pre-wired FastAPI application.

    This is the primary entry point for using boring-ui backend.
    All dependencies are injectable for testing and customization.

    Args:
        config: API configuration. Defaults to current directory as workspace.
        storage: Storage backend. Defaults to LocalStorage.
        approval_store: Approval store. Defaults to InMemoryApprovalStore.
        include_pty: Include PTY WebSocket router (default: True)
        include_stream: Include Claude stream WebSocket router (default: True)
        include_approval: Include approval workflow router (default: True)
        routers: List of router names to include. If None, uses include_* flags.
            Valid names: 'files', 'git', 'pty', 'stream', 'approval'
        registry: Custom router registry. Defaults to create_default_registry().

    Returns:
        Configured FastAPI application with all routes mounted.

    Example:
        # Minimal usage
        app = create_app()

        # Custom configuration
        config = APIConfig(
            workspace_root=Path('/my/project'),
            cors_origins=['https://myapp.com'],
        )
        app = create_app(config)

        # With custom storage
        from myapp.storage import RedisStorage
        app = create_app(storage=RedisStorage())

        # Minimal app (no WebSockets)
        app = create_app(include_pty=False, include_stream=False)

        # Using router list (alternative to include_* flags)
        app = create_app(routers=['files', 'git'])  # Only file and git routes
    """
    # Apply defaults
    config = config or APIConfig(workspace_root=Path.cwd())
    storage = storage or LocalStorage(config.workspace_root)
    approval_store = approval_store or InMemoryApprovalStore()
    registry = registry or create_default_registry()

    # Determine which routers to include
    # If routers list is provided, use it; otherwise use include_* flags
    if routers is not None:
        enabled_routers = set(routers)
    else:
        enabled_routers = {'files', 'git'}  # Core routers always included
        if include_pty:
            enabled_routers.add('pty')
        if include_stream:
            enabled_routers.add('stream')
        if include_approval:
            enabled_routers.add('approval')

    # Build enabled features map for capabilities endpoint
    enabled_features = {
        'files': 'files' in enabled_routers,
        'git': 'git' in enabled_routers,
        'pty': 'pty' in enabled_routers,
        'stream': 'stream' in enabled_routers,
        'approval': 'approval' in enabled_routers,
    }

    # Create app
    app = FastAPI(
        title='Boring UI API',
        description='A composition-based web IDE backend',
        version='0.1.0',
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    # Mount routers from registry based on enabled set
    router_args = {
        'files': (config, storage),
        'git': (config,),
        'pty': (config,),
        'stream': (config,),
        'approval': (approval_store,),
    }

    for router_name in enabled_routers:
        entry = registry.get(router_name)
        if entry:
            info, factory = entry
            args = router_args.get(router_name, ())
            app.include_router(factory(*args), prefix=info.prefix)

    # Always include capabilities router
    app.include_router(
        create_capabilities_router(enabled_features, registry),
        prefix='/api',
    )

    # Health check
    @app.get('/health')
    async def health():
        """Health check endpoint."""
        return {
            'status': 'ok',
            'workspace': str(config.workspace_root),
            'features': enabled_features,
        }

    # API info
    @app.get('/api/config')
    async def get_config():
        """Get API configuration info."""
        return {
            'workspace_root': str(config.workspace_root),
            'pty_providers': list(config.pty_providers.keys()),
            'paths': {
                'files': '.',
            },
        }

    # Project endpoint (expected by frontend)
    @app.get('/api/project')
    async def get_project():
        """Get project root for the frontend."""
        return {
            'root': str(config.workspace_root),
        }

    # Claude session endpoints (aligned with kurt-core)
    @app.get('/api/sessions')
    async def list_sessions():
        """List active Claude stream sessions."""
        from .stream_bridge import _SESSION_REGISTRY
        return {
            'sessions': [
                {
                    'id': session_id,
                    'alive': session.is_alive(),
                    'clients': len(session.clients),
                    'history_count': len(session.history),
                }
                for session_id, session in _SESSION_REGISTRY.items()
            ],
        }

    @app.post('/api/sessions')
    async def create_session():
        """Create a new session ID (client will connect via WebSocket)."""
        import uuid
        return {'session_id': str(uuid.uuid4())}

    return app
