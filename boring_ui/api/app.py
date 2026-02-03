"""Application factory for boring-ui API."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APIConfig
from .storage import Storage, LocalStorage
from .file_routes import create_file_router
from .git_routes import create_git_router
from .pty_bridge import create_pty_router
from .stream_bridge import create_stream_router
from .approval import ApprovalStore, InMemoryApprovalStore, create_approval_router


def create_app(
    config: APIConfig | None = None,
    storage: Storage | None = None,
    approval_store: ApprovalStore | None = None,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
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
    """
    # Apply defaults
    config = config or APIConfig(workspace_root=Path.cwd())
    storage = storage or LocalStorage(config.workspace_root)
    approval_store = approval_store or InMemoryApprovalStore()

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

    # Mount core routers
    app.include_router(create_file_router(config, storage), prefix='/api')
    app.include_router(create_git_router(config), prefix='/api/git')

    # Optional routers
    if include_pty:
        app.include_router(create_pty_router(config), prefix='/ws')

    if include_stream:
        app.include_router(create_stream_router(config), prefix='/ws')

    if include_approval:
        app.include_router(create_approval_router(approval_store), prefix='/api')

    # Health check
    @app.get('/health')
    async def health():
        """Health check endpoint."""
        return {
            'status': 'ok',
            'workspace': str(config.workspace_root),
            'features': {
                'pty': include_pty,
                'stream': include_stream,
                'approval': include_approval,
            },
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

    return app
