"""Configuration for boring-ui API."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse


def _default_cors_origins() -> list[str]:
    """Get default CORS origins, supporting env override."""
    env_origins = os.environ.get('CORS_ORIGINS', '')
    if env_origins:
        return [o.strip() for o in env_origins.split(',') if o.strip()]
    # Default: allow common dev origins
    return [
        'http://localhost:5173',
        'http://localhost:5174',
        'http://localhost:5175',
        'http://localhost:3000',
        'http://127.0.0.1:5173',
        'http://127.0.0.1:5174',
        'http://127.0.0.1:5175',
        '*',  # Allow all origins in dev - restrict in production
    ]


TRUE_VALUES = {'1', 'true', 'yes', 'on'}
FALSE_VALUES = {'0', 'false', 'no', 'off'}
VALID_WORKSPACE_MODES = {'local', 'sandbox'}
VALID_ROUTING_MODES = {'single_tenant', 'per_user'}

# Sprite filesystem layout defaults (V0 plan §"Sprite filesystem layout")
DEFAULT_SPRITE_WORKSPACE = Path('/home/sprite/workspace')
DEFAULT_SPRITE_SERVICE_ROOT = Path('/srv/workspace-api')
DEFAULT_SPRITE_SECRETS_DIR = Path('/home/sprite/.auth')


@dataclass(frozen=True)
class SpriteLayout:
    """Sprite filesystem boundary configuration.

    Enforces separation between user workspace and service runtime/secrets
    directories. Workspace root for file tools must not overlap with
    protected paths.
    """

    workspace_root: Path = DEFAULT_SPRITE_WORKSPACE
    service_root: Path = DEFAULT_SPRITE_SERVICE_ROOT
    secrets_dir: Path = DEFAULT_SPRITE_SECRETS_DIR

    @property
    def protected_paths(self) -> list[Path]:
        """Paths that must not overlap with workspace_root."""
        return [self.service_root, self.secrets_dir]


class ConfigValidationError(ValueError):
    """Raised when startup configuration is invalid."""

    def __init__(self, issues: list[str]):
        self.issues = issues
        formatted = '\n'.join(f'- {issue}' for issue in issues)
        super().__init__(f'Invalid startup configuration:\n{formatted}')


def _parse_bool(value: str | None, var_name: str, issues: list[str], *, default: bool = False) -> bool:
    """Parse an environment boolean with strict accepted values."""
    if value is None or value.strip() == '':
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    issues.append(
        f'{var_name} must be a boolean (one of: 1/0, true/false, yes/no, on/off), got {value!r}.'
    )
    return default


def _require_env(
    env: Mapping[str, str],
    key: str,
    issues: list[str],
    *,
    mode_hint: str = 'sandbox mode',
) -> str:
    """Read a required env var and emit a clear issue when missing."""
    value = env.get(key, '').strip()
    if value:
        return value
    issues.append(f'{key} is required for {mode_hint}.')
    return ''


def _paths_overlap(a: Path, b: Path) -> bool:
    """Check if two paths overlap (one is a prefix of the other)."""
    try:
        a_resolved = a.resolve()
        b_resolved = b.resolve()
    except OSError:
        # If we can't resolve (path doesn't exist yet), use as-is
        a_resolved = a
        b_resolved = b
    return a_resolved == b_resolved or b_resolved.is_relative_to(a_resolved) or a_resolved.is_relative_to(b_resolved)


def validate_workspace_boundaries(
    workspace_root: Path,
    layout: SpriteLayout | None = None,
) -> list[str]:
    """Validate that workspace_root does not overlap with protected paths.

    Returns a list of issue strings (empty if valid).
    """
    layout = layout or SpriteLayout()
    issues: list[str] = []
    for protected in layout.protected_paths:
        if _paths_overlap(workspace_root, protected):
            issues.append(
                f'SANDBOX_WORKSPACE_ROOT ({workspace_root}) overlaps with protected path {protected}. '
                f'Workspace must be separate from service runtime and secrets directories.'
            )
    return issues


@dataclass(frozen=True)
class SandboxServiceTarget:
    """Workspace service routing target inside sandbox mode."""

    host: str
    port: int
    path: str


@dataclass(frozen=True)
class SandboxConfig:
    """Validated sandbox runtime configuration."""

    base_url: str
    sprite_name: str
    api_token: str
    session_token_secret: str
    service_target: SandboxServiceTarget
    multi_tenant: bool = False
    routing_mode: str = 'single_tenant'
    auth_identity_binding: bool = False
    sprite_layout: SpriteLayout = field(default_factory=SpriteLayout)


@dataclass(frozen=True)
class RuntimeConfig:
    """Validated runtime mode and optional sandbox settings."""

    workspace_mode: str = 'local'
    sandbox: SandboxConfig | None = None


def load_runtime_config(env: Mapping[str, str] | None = None) -> RuntimeConfig:
    """Load and validate startup runtime configuration from environment."""
    env = os.environ if env is None else env
    issues: list[str] = []

    workspace_mode = env.get('WORKSPACE_MODE', 'local').strip().lower()
    if workspace_mode not in VALID_WORKSPACE_MODES:
        issues.append(
            f"WORKSPACE_MODE must be one of {sorted(VALID_WORKSPACE_MODES)}, got {workspace_mode!r}."
        )
        raise ConfigValidationError(issues)

    if workspace_mode == 'local':
        return RuntimeConfig(workspace_mode='local', sandbox=None)

    base_url = _require_env(env, 'SPRITES_BASE_URL', issues)
    sprite_name = _require_env(env, 'SPRITES_SPRITE_NAME', issues)
    api_token = _require_env(env, 'SPRITES_API_TOKEN', issues)
    session_token_secret = _require_env(env, 'SESSION_TOKEN_SECRET', issues)
    service_host = _require_env(env, 'SPRITES_WORKSPACE_SERVICE_HOST', issues)
    service_port_raw = _require_env(env, 'SPRITES_WORKSPACE_SERVICE_PORT', issues)
    service_path = env.get('SPRITES_WORKSPACE_SERVICE_PATH', '/').strip() or '/'

    multi_tenant = _parse_bool(env.get('MULTI_TENANT'), 'MULTI_TENANT', issues, default=False)
    route_by_user = _parse_bool(env.get('ROUTE_BY_USER'), 'ROUTE_BY_USER', issues, default=False)
    auth_identity_binding = _parse_bool(
        env.get('AUTH_IDENTITY_BINDING_ENABLED'),
        'AUTH_IDENTITY_BINDING_ENABLED',
        issues,
        default=False,
    )

    routing_mode = env.get('WORKSPACE_ROUTING_MODE', 'single_tenant').strip().lower()
    if routing_mode not in VALID_ROUTING_MODES:
        issues.append(
            f"WORKSPACE_ROUTING_MODE must be one of {sorted(VALID_ROUTING_MODES)}, got {routing_mode!r}."
        )

    if service_path and not service_path.startswith('/'):
        issues.append('SPRITES_WORKSPACE_SERVICE_PATH must start with "/" (example: /workspace).')

    service_port = 0
    if service_port_raw:
        try:
            service_port = int(service_port_raw)
            if not 1 <= service_port <= 65535:
                issues.append(
                    f'SPRITES_WORKSPACE_SERVICE_PORT must be between 1 and 65535, got {service_port}.'
                )
        except ValueError:
            issues.append(
                f'SPRITES_WORKSPACE_SERVICE_PORT must be an integer, got {service_port_raw!r}.'
            )

    if session_token_secret and len(session_token_secret) < 32:
        issues.append('SESSION_TOKEN_SECRET must be at least 32 characters.')

    if base_url:
        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            issues.append(
                f"SPRITES_BASE_URL must be an absolute URL like 'https://host', got {base_url!r}."
            )

    multi_tenant_indicators_present = multi_tenant or route_by_user or routing_mode == 'per_user'
    if multi_tenant_indicators_present and not auth_identity_binding:
        issues.append(
            'Multi-tenant sandbox mode is not supported unless authenticated identity binding is enabled. '
            'Set AUTH_IDENTITY_BINDING_ENABLED=true or disable multi-tenant indicators '
            '(MULTI_TENANT, ROUTE_BY_USER, WORKSPACE_ROUTING_MODE=per_user).'
        )

    # Sprite filesystem layout boundaries
    workspace_root_str = env.get('SANDBOX_WORKSPACE_ROOT', '').strip()
    service_root_str = env.get('SANDBOX_SERVICE_ROOT', '').strip()
    secrets_dir_str = env.get('SANDBOX_SECRETS_DIR', '').strip()
    sprite_layout = SpriteLayout(
        workspace_root=Path(workspace_root_str) if workspace_root_str else DEFAULT_SPRITE_WORKSPACE,
        service_root=Path(service_root_str) if service_root_str else DEFAULT_SPRITE_SERVICE_ROOT,
        secrets_dir=Path(secrets_dir_str) if secrets_dir_str else DEFAULT_SPRITE_SECRETS_DIR,
    )
    issues.extend(validate_workspace_boundaries(sprite_layout.workspace_root, sprite_layout))

    if issues:
        raise ConfigValidationError(issues)

    return RuntimeConfig(
        workspace_mode='sandbox',
        sandbox=SandboxConfig(
            base_url=base_url,
            sprite_name=sprite_name,
            api_token=api_token,
            session_token_secret=session_token_secret,
            service_target=SandboxServiceTarget(
                host=service_host,
                port=service_port,
                path=service_path,
            ),
            multi_tenant=multi_tenant,
            routing_mode=routing_mode,
            auth_identity_binding=auth_identity_binding,
            sprite_layout=sprite_layout,
        ),
    )


@dataclass
class APIConfig:
    """Central configuration for all API routers.

    This dataclass is passed to all create_*_router() factories,
    enabling dependency injection and avoiding global state.
    """
    workspace_root: Path
    cors_origins: list[str] = field(default_factory=_default_cors_origins)

    # PTY provider configuration: provider_name -> command list
    # e.g., 'shell' -> ['bash'], 'claude' -> ['claude', '--dangerously-skip-permissions']
    pty_providers: dict[str, list[str]] = field(default_factory=lambda: {
        'shell': ['bash'],
        'claude': ['claude', '--dangerously-skip-permissions'],
    })

    def validate_path(self, path: Path | str) -> Path:
        """Validate that a path is within workspace_root.

        This is CRITICAL for security - prevents path traversal attacks.
        All file operations must use this before accessing the filesystem.

        Args:
            path: Path to validate (relative or absolute)

        Returns:
            Resolved absolute path within workspace_root

        Raises:
            ValueError: If path escapes workspace_root
        """
        if isinstance(path, str):
            path = Path(path)

        # Resolve to absolute, handling .. and symlinks
        resolved = (self.workspace_root / path).resolve()

        # Ensure it's within workspace
        if not resolved.is_relative_to(self.workspace_root.resolve()):
            raise ValueError(f'Path traversal detected: {path}')

        return resolved
