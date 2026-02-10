"""Application factory for boring-ui API."""
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APIConfig, get_cors_origin
from .storage import Storage, LocalStorage
from .modules.files import create_file_router
from .modules.git import create_git_router
from .modules.pty import create_pty_router
from .modules.stream import create_stream_router
from .modules.sandbox import SandboxManager, create_provider
from .approval import ApprovalStore, InMemoryApprovalStore, create_approval_router
from .auth import ServiceTokenIssuer
from .capabilities import (
    RouterRegistry,
    ServiceConnectionInfo,
    create_default_registry,
    create_capabilities_router,
)

# Global sandbox manager (for lifespan management)
_sandbox_manager: SandboxManager | None = None


def create_app(
    config: APIConfig | None = None,
    storage: Storage | None = None,
    approval_store: ApprovalStore | None = None,
    sandbox_manager: SandboxManager | None = None,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
    include_sandbox: bool = False,
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
        include_sandbox: Include sandbox-agent router (default: False)
        routers: List of router names to include. If None, uses include_* flags.
            Valid names: 'files', 'git', 'pty', 'stream', 'approval', 'sandbox'
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
    global _sandbox_manager

    # Apply defaults
    config = config or APIConfig(workspace_root=Path.cwd())
    storage = storage or LocalStorage(config.workspace_root)
    approval_store = approval_store or InMemoryApprovalStore()
    registry = registry or create_default_registry()

    # Generate per-session auth token for sandbox-agent Direct Connect
    sandbox_auth_token = secrets.token_hex(16)
    cors_origin = get_cors_origin()

    # Create sandbox manager if needed
    if sandbox_manager is None and (include_sandbox or (routers and 'sandbox' in routers)):
        sandbox_config = {
            'SANDBOX_PROVIDER': os.environ.get('SANDBOX_PROVIDER', 'local'),
            'SANDBOX_PORT': os.environ.get('SANDBOX_PORT', '2468'),
            'SANDBOX_WORKSPACE': os.environ.get('SANDBOX_WORKSPACE', str(config.workspace_root)),
            'SANDBOX_TOKEN': sandbox_auth_token,
            'SANDBOX_CORS_ORIGIN': cors_origin,
        }
        sandbox_manager = SandboxManager(
            create_provider(sandbox_config),
            service_token=sandbox_auth_token,
        )
        _sandbox_manager = sandbox_manager

    # Determine which routers to include
    # If routers list is provided, use it; otherwise use include_* flags
    if routers is not None:
        enabled_routers = set(routers)
    else:
        enabled_routers = {'files', 'git'}  # Core routers always included
        if include_pty:
            enabled_routers.add('pty')
        if include_stream:
            # Use new canonical name, but 'stream' also works via registry alias
            enabled_routers.add('chat_claude_code')
        if include_approval:
            enabled_routers.add('approval')
        if include_sandbox:
            enabled_routers.add('sandbox')

    # Support 'stream' alias -> 'chat_claude_code' for backward compatibility
    if 'stream' in enabled_routers:
        enabled_routers.add('chat_claude_code')

    # Build enabled features map for capabilities endpoint
    # Include both names for backward compatibility
    chat_enabled = 'chat_claude_code' in enabled_routers or 'stream' in enabled_routers
    enabled_features = {
        'files': 'files' in enabled_routers,
        'git': 'git' in enabled_routers,
        'pty': 'pty' in enabled_routers,
        'chat_claude_code': chat_enabled,
        'stream': chat_enabled,  # Backward compatibility alias
        'approval': 'approval' in enabled_routers,
        'sandbox': 'sandbox' in enabled_routers,
    }

    # Lifespan handler for cleanup
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        yield
        # Shutdown - cleanup sandbox
        if sandbox_manager:
            try:
                await sandbox_manager.shutdown()
            except Exception:
                pass  # Best effort cleanup

    # Create app
    app = FastAPI(
        title='Boring UI API',
        description='A composition-based web IDE backend',
        version='0.1.0',
        lifespan=lifespan,
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
        'chat_claude_code': (config,),
        'stream': (config,),  # Alias
        'approval': (approval_store,),
        'sandbox': (sandbox_manager,) if sandbox_manager else (),
    }

    # Track mounted factories to avoid double-mounting aliases
    # (stream and chat_claude_code use the same factory, but pty uses a different one)
    mounted_factories: set[int] = set()

    for router_name in enabled_routers:
        entry = registry.get(router_name)
        if entry:
            info, factory = entry
            # Skip if this factory is already mounted (avoids duplicate alias mounts)
            factory_id = id(factory)
            if factory_id in mounted_factories:
                continue
            mounted_factories.add(factory_id)
            args = router_args.get(router_name, ())
            app.include_router(factory(*args), prefix=info.prefix)

    # Build service connection registry for Direct Connect
    token_issuer = ServiceTokenIssuer()
    service_registry: dict[str, ServiceConnectionInfo] = {}

    if 'sandbox' in enabled_routers and sandbox_manager:
        # Derive URL from provider's configured port
        sandbox_port = getattr(sandbox_manager.provider, 'port', 2468)
        service_registry['sandbox'] = ServiceConnectionInfo(
            name='sandbox',
            url=f'http://127.0.0.1:{sandbox_port}',
            token=sandbox_auth_token,  # Static token matching --token flag
            qp_token=sandbox_auth_token,  # Same token for SSE/WS
            protocol='rest+sse',
        )

    # Always include capabilities router
    app.include_router(
        create_capabilities_router(
            enabled_features,
            registry,
            token_issuer=token_issuer if service_registry else None,
            service_registry=service_registry or None,
        ),
        prefix='/api',
    )

    # Store token issuer on app state for use by other components
    app.state.token_issuer = token_issuer

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
        from .modules.stream import get_session_registry as get_stream_registry
        from .modules.pty import get_session_registry as get_pty_registry

        # Combine PTY and stream sessions
        pty_sessions = [
            {
                'id': session_id,
                'type': 'pty',
                'alive': session.is_alive(),
                'clients': len(session.clients),
                'history_count': len(session.history),
            }
            for session_id, session in get_pty_registry().items()
        ]
        stream_sessions = [
            {
                'id': session_id,
                'type': 'stream',
                'alive': session.is_alive(),
                'clients': len(session.clients),
                'history_count': len(session.history),
            }
            for session_id, session in get_stream_registry().items()
        ]
        return {'sessions': pty_sessions + stream_sessions}

    @app.post('/api/sessions')
    async def create_session():
        """Create a new session ID (client will connect via WebSocket)."""
        import uuid
        return {'session_id': str(uuid.uuid4())}

    return app
