"""Application factory for boring-ui API."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import APIConfig, RuntimeConfig, load_runtime_config
from .storage import Storage, LocalStorage
from .modules.files import create_file_router
from .modules.git import create_git_router
from .modules.pty import create_pty_router
from .modules.stream import create_stream_router
from .modules.sandbox import InMemorySandboxStore, SandboxStore, TargetResolver
from .approval import ApprovalStore, InMemoryApprovalStore, create_approval_router
from .workspace_gateway import create_workspace_gateway
from .capabilities import (
    RouterRegistry,
    create_default_registry,
    create_capabilities_router,
)


def create_app(
    config: APIConfig | None = None,
    runtime_config: RuntimeConfig | None = None,
    storage: Storage | None = None,
    approval_store: ApprovalStore | None = None,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
    include_sandbox: bool = True,
    sandbox_store: SandboxStore | None = None,
    routers: list[str] | None = None,
    registry: RouterRegistry | None = None,
) -> FastAPI:
    """Create a pre-wired FastAPI application.

    This is the primary entry point for using boring-ui backend.
    All dependencies are injectable for testing and customization.

    Args:
        config: API configuration. Defaults to current directory as workspace.
        storage: Storage backend. Defaults to LocalStorage.
        runtime_config: Runtime mode/config loaded from environment when omitted.
        approval_store: Approval store. Defaults to InMemoryApprovalStore.
        include_pty: Include PTY WebSocket router (default: True)
        include_stream: Include Claude stream WebSocket router (default: True)
        include_approval: Include approval workflow router (default: True)
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
    # Apply defaults
    config = config or APIConfig(workspace_root=Path.cwd())
    storage = storage or LocalStorage(config.workspace_root)
    runtime_config = runtime_config or load_runtime_config()
    approval_store = approval_store or InMemoryApprovalStore()
    sandbox_store = sandbox_store or InMemorySandboxStore()
    target_resolver = TargetResolver(store=sandbox_store)
    registry = registry or create_default_registry()
    workspace_gateway = create_workspace_gateway(
        api_config=config,
        runtime_config=runtime_config,
        storage=storage,
    )

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
    app.state.runtime_config = runtime_config
    app.state.workspace_gateway = workspace_gateway

    # Mount routers from registry based on enabled set
    router_args = {
        'files': (config, storage),
        'git': (config,),
        'pty': (config,),
        'chat_claude_code': (config,),
        'stream': (config,),  # Alias
        'approval': (approval_store,),
        'sandbox': (sandbox_store, target_resolver),
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
            'workspace_mode': runtime_config.workspace_mode,
            'features': enabled_features,
        }

    # API info
    @app.get('/api/config')
    async def get_config():
        """Get API configuration info."""
        response = {
            'workspace_root': str(config.workspace_root),
            'workspace_mode': runtime_config.workspace_mode,
            'pty_providers': list(config.pty_providers.keys()),
            'paths': {
                'files': '.',
            },
        }
        if runtime_config.sandbox:
            response['sandbox'] = {
                'base_url': runtime_config.sandbox.base_url,
                'sprite_name': runtime_config.sandbox.sprite_name,
                'service_target': {
                    'host': runtime_config.sandbox.service_target.host,
                    'port': runtime_config.sandbox.service_target.port,
                    'path': runtime_config.sandbox.service_target.path,
                },
                'multi_tenant': runtime_config.sandbox.multi_tenant,
                'routing_mode': runtime_config.sandbox.routing_mode,
                'auth_identity_binding': runtime_config.sandbox.auth_identity_binding,
            }
        return response

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
