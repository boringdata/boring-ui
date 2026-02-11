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
from .modules.companion import CompanionManager, create_companion_provider
from .approval import ApprovalStore, InMemoryApprovalStore, create_approval_router
from .auth import ServiceTokenIssuer
from .capabilities import (
    RouterRegistry,
    ServiceConnectionInfo,
    create_default_registry,
    create_capabilities_router,
)

# Global managers (for lifespan management)
_sandbox_manager: SandboxManager | None = None
_companion_manager: CompanionManager | None = None


def _get_routers_for_mode(
    run_mode: str,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
    include_sandbox: bool = False,
    include_companion: bool = False,
) -> set[str]:
    """Determine which routers to mount based on run mode.

    LOCAL mode: All routers available (dev/local workflows)
    HOSTED mode: Only capabilities and config (no direct privileged access)

    Args:
        run_mode: 'local' or 'hosted'
        include_*: Feature flags for LOCAL mode only (ignored in HOSTED)

    Returns:
        Set of router names to mount
    """
    enabled = {'files', 'git'}  # Core routers always in LOCAL mode

    if run_mode == 'local':
        # LOCAL mode: mount all requested routers
        if include_pty:
            enabled.add('pty')
        if include_stream:
            enabled.add('chat_claude_code')
        if include_approval:
            enabled.add('approval')
        if include_sandbox:
            enabled.add('sandbox')
        if include_companion:
            enabled.add('companion')
    elif run_mode == 'hosted':
        # HOSTED mode: only safe control-plane routers
        # - approval: tool approval workflow (safe for untrusted clients)
        # No direct file/git/pty/chat/exec access in hosted mode.
        # These will be provided via:
        # - Hosted Auth (bd-1pwb.2) for control plane
        # - Sandbox Internal API (bd-1pwb.4) for data plane
        # - Hosted Proxy Layer (bd-1pwb.5) for client access
        enabled = {'approval'}
    else:
        raise ValueError(f"Unknown run mode: {run_mode}")

    return enabled


def create_app(
    config: APIConfig | None = None,
    storage: Storage | None = None,
    approval_store: ApprovalStore | None = None,
    sandbox_manager: SandboxManager | None = None,
    include_pty: bool = True,
    include_stream: bool = True,
    include_approval: bool = True,
    include_sandbox: bool = False,
    include_companion: bool = False,
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
        include_companion: Include Companion server router (default: False)
        routers: List of router names to include. If None, uses include_* flags.
            Valid names: 'files', 'git', 'pty', 'stream', 'approval', 'sandbox', 'companion'
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
    global _sandbox_manager, _companion_manager

    # Apply defaults
    if config is None:
        # workspace_root can be configured via WORKSPACE_ROOT env var
        # This allows pointing to local, sprites, or any filesystem
        workspace = Path(os.environ.get('WORKSPACE_ROOT', Path.cwd()))
        workspace.mkdir(parents=True, exist_ok=True)
        config = APIConfig(workspace_root=workspace)

    # Validate configuration at startup (fail-fast)
    try:
        config.validate_startup()
    except ValueError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error('Configuration validation failed: %s', e)
        raise

    storage = storage or LocalStorage(config.workspace_root)
    approval_store = approval_store or InMemoryApprovalStore()
    registry = registry or create_default_registry()

    # Auth infrastructure: token issuer (JWT) + static token for sandbox
    token_issuer = ServiceTokenIssuer()
    sandbox_auth_token = secrets.token_hex(16)
    cors_origin = get_cors_origin()

    # Get external host for service URLs (e.g., from browser on different machine)
    import subprocess
    external_host = os.environ.get('EXTERNAL_HOST')
    if not external_host:
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                ips = result.stdout.strip().split()
                for ip in ips:
                    if ip and not ip.startswith('127.') and not ip.startswith('::'):
                        external_host = ip
                        break
        except Exception:
            pass
    if not external_host:
        external_host = '127.0.0.1'

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

    # Create companion manager if needed
    companion_manager: CompanionManager | None = None
    if include_companion or (routers and 'companion' in routers):
        companion_config = {
            'COMPANION_PORT': os.environ.get('COMPANION_PORT', '3456'),
            'COMPANION_WORKSPACE': os.environ.get('COMPANION_WORKSPACE', str(config.workspace_root)),
            'COMPANION_SIGNING_KEY': token_issuer.signing_key_hex,
            'COMPANION_CORS_ORIGIN': cors_origin,
            'COMPANION_EXTERNAL_HOST': external_host,
        }
        server_dir = os.environ.get('COMPANION_SERVER_DIR')
        if server_dir:
            companion_config['COMPANION_SERVER_DIR'] = server_dir
        companion_manager = CompanionManager(
            create_companion_provider(companion_config),
            service_token=token_issuer.signing_key_hex,
        )
        _companion_manager = companion_manager

    # Determine which routers to include based on mode
    # Mode-aware composition: explicit paths, no hidden fallbacks
    import logging
    logger = logging.getLogger(__name__)

    if routers is not None:
        # User provided explicit router list - honor it
        enabled_routers = set(routers)
        # In HOSTED mode, warn if privileged routers requested
        if config.run_mode.value == 'hosted':
            privileged = {'files', 'git', 'pty', 'chat_claude_code', 'stream', 'sandbox', 'companion'}
            requested_privileged = privileged & enabled_routers
            if requested_privileged:
                raise ValueError(
                    f"SECURITY: Hosted mode cannot mount privileged routers. "
                    f"Requested: {', '.join(sorted(requested_privileged))}. "
                    f"These operations must be routed through Hosted Auth and Sandbox APIs (phases 2-5)."
                )
    else:
        # Use mode-based defaults
        enabled_routers = _get_routers_for_mode(
            config.run_mode.value,
            include_pty=include_pty,
            include_stream=include_stream,
            include_approval=include_approval,
            include_sandbox=include_sandbox,
            include_companion=include_companion,
        )
        # In HOSTED mode, log which routers would have been included in LOCAL
        if config.run_mode.value == 'hosted':
            local_routers = _get_routers_for_mode(
                'local',
                include_pty=include_pty,
                include_stream=include_stream,
                include_approval=include_approval,
                include_sandbox=include_sandbox,
                include_companion=include_companion,
            )
            deferred = local_routers - enabled_routers
            if deferred:
                logger.info(
                    'HOSTED mode defers privileged routers to later phases: %s. '
                    'Control plane uses only: %s.',
                    ', '.join(sorted(deferred)),
                    ', '.join(sorted(enabled_routers or ['capabilities']))
                )

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
        'companion': 'companion' in enabled_routers,
    }

    # Lifespan handler for startup/cleanup
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup — log configuration and launch managed subprocesses
        import logging
        logger = logging.getLogger(__name__)
        logger.info('Boring UI API startup')
        logger.info('Run mode: %s', config.run_mode.value.upper())
        logger.info('Workspace root: %s', config.workspace_root)
        logger.info('Enabled features: %s', ', '.join(
            k for k, v in enabled_features.items() if v
        ))

        if companion_manager:
            try:
                await companion_manager.ensure_running()
            except Exception as exc:
                logger.warning(
                    'Companion auto-start failed: %s', exc,
                )
        yield
        # Shutdown - cleanup managed subprocesses
        if sandbox_manager:
            try:
                await sandbox_manager.shutdown()
            except Exception:
                pass  # Best effort cleanup
        if companion_manager:
            try:
                await companion_manager.shutdown()
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
        'companion': (companion_manager,) if companion_manager else (),
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
    service_registry: dict[str, ServiceConnectionInfo] = {}

    if 'sandbox' in enabled_routers and sandbox_manager:
        # Derive URL from provider's configured port
        sandbox_port = getattr(sandbox_manager.provider, 'port', 2468)
        service_registry['sandbox'] = ServiceConnectionInfo(
            name='sandbox',
            url=f'http://{external_host}:{sandbox_port}',
            token=sandbox_auth_token,  # Static token matching --token flag
            qp_token=sandbox_auth_token,  # Same token for SSE/WS
            protocol='rest+sse',
        )

    if 'companion' in enabled_routers and companion_manager:
        companion_port = companion_manager.provider.port
        service_registry['companion'] = ServiceConnectionInfo(
            name='companion',
            url=f'http://{external_host}:{companion_port}',
            token='',  # JWT issued per-request by token_issuer
            qp_token='',
            protocol='rest+sse',
        )

    # Always include capabilities router (provides mode metadata)
    app.include_router(
        create_capabilities_router(
            enabled_features,
            registry,
            token_issuer=token_issuer if service_registry else None,
            service_registry=service_registry or None,
            filesystem_source=config.filesystem_source,
            run_mode=config.run_mode.value,
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
