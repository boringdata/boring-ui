"""Configuration for boring-ui API."""
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RunMode(str, Enum):
    """Execution mode for boring-ui backend.

    - LOCAL: Single backend with direct operations (dev/local)
    - HOSTED: Dual API model with control plane (public) and data plane (private)
    """
    LOCAL = 'local'
    HOSTED = 'hosted'

    @classmethod
    def from_env(cls) -> 'RunMode':
        """Get run mode from BORING_UI_RUN_MODE env var.

        Defaults to LOCAL if not specified.
        Case-insensitive.
        """
        mode_str = os.environ.get('BORING_UI_RUN_MODE', 'local').lower()
        try:
            return cls(mode_str)
        except ValueError:
            raise ValueError(
                f"Invalid BORING_UI_RUN_MODE='{mode_str}'. "
                f"Must be one of: {', '.join(m.value for m in cls)}"
            )


class SandboxProvider(str, Enum):
    """Sandbox provider for workspace operations.

    - LOCAL: In-process or local subprocess (dev/local)
    - SANDBOX: Sandbox.dev API
    - SPRITES: Sprites.dev API (hosted remote)
    """
    LOCAL = 'local'
    SANDBOX = 'sandbox'
    SPRITES = 'sprites'

    @classmethod
    def from_env(cls) -> 'SandboxProvider':
        """Get sandbox provider from SANDBOX_PROVIDER env var.

        Defaults to LOCAL if not specified.
        Case-insensitive.
        """
        provider_str = os.environ.get('SANDBOX_PROVIDER', 'local').lower()
        try:
            return cls(provider_str)
        except ValueError:
            raise ValueError(
                f"Invalid SANDBOX_PROVIDER='{provider_str}'. "
                f"Must be one of: {', '.join(p.value for p in cls)}"
            )


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


def get_cors_origin() -> str:
    """Detect the CORS origin to pass to chat service subprocesses.

    Services need to know which browser origin to accept requests from.
    This is passed via CORS_ORIGIN env var to subprocesses.

    Priority:
      1. CORS_ORIGIN env var (explicit override)
      2. VITE_DEV_ORIGIN env var (set by dev tooling)
      3. Default dev origin (http://localhost:5173)
    """
    explicit = os.environ.get('CORS_ORIGIN', '').strip()
    if explicit:
        return explicit

    vite_origin = os.environ.get('VITE_DEV_ORIGIN', '').strip()
    if vite_origin:
        return vite_origin

    return 'http://localhost:5173'


def is_dev_auth_bypass_enabled() -> bool:
    """Return True when hosted auth bypass is explicitly enabled.

    This is for local development only and must never be used in production.
    """
    raw = os.environ.get('DEV_AUTH_BYPASS', '').strip().lower()
    return raw in {'1', 'true', 'yes', 'on'}


def is_local_parity_mode() -> bool:
    """Return True when LOCAL mode should use HTTP parity transport (bd-1adh.7.2).

    When enabled, LOCAL mode routes /internal/v1/* calls through
    HTTPInternalTransport to a co-located local-api HTTP server instead
    of in-process mounting. This exercises the same code path as hosted
    mode for integration testing.

    Set LOCAL_PARITY_MODE=http to enable.
    """
    raw = os.environ.get('LOCAL_PARITY_MODE', '').strip().lower()
    return raw == 'http'


@dataclass
class APIConfig:
    """Central configuration for all API routers.

    This dataclass is passed to all create_*_router() factories,
    enabling dependency injection and avoiding global state.
    """
    workspace_root: Path
    run_mode: RunMode = field(default_factory=RunMode.from_env)
    sandbox_provider: SandboxProvider = field(default_factory=SandboxProvider.from_env)
    cors_origins: list[str] = field(default_factory=_default_cors_origins)

    # Filesystem source: 'local', 'sandbox', or 'sprites'
    # Determines where FileTree loads files from
    filesystem_source: str = field(default_factory=lambda: os.environ.get('FILESYSTEM_SOURCE', 'local'))

    # PTY provider configuration: provider_name -> command list
    # e.g., 'shell' -> ['bash'], 'claude' -> ['claude', '--dangerously-skip-permissions']
    pty_providers: dict[str, list[str]] = field(default_factory=lambda: {
        'shell': ['bash'],
        'claude': ['claude', '--dangerously-skip-permissions'],
    })

    # OIDC configuration (for hosted mode JWT verification)
    # Environment variables:
    #   OIDC_ISSUER: IdP issuer URL (e.g., https://auth.example.com)
    #   OIDC_AUDIENCE: Expected audience claim
    #   OIDC_CACHE_TTL_SECONDS: JWKS cache lifetime (default 3600)
    oidc_issuer: str | None = field(default_factory=lambda: os.environ.get('OIDC_ISSUER'))
    oidc_audience: str | None = field(default_factory=lambda: os.environ.get('OIDC_AUDIENCE'))
    oidc_cache_ttl_seconds: int = field(default_factory=lambda: int(os.environ.get('OIDC_CACHE_TTL_SECONDS', '3600')))

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

    def _get_required_env_vars(self) -> dict[str, dict[str, list[str]]]:
        """Get required environment variables per mode and provider combination.

        Returns:
            dict mapping mode -> provider -> list of required env vars
        """
        hosted_required = [
            'WORKSPACE_ROOT',  # Required for all modes
            'OIDC_ISSUER',  # JWT issuer for edge auth
            'OIDC_AUDIENCE',  # JWT audience for edge auth
        ]
        if is_dev_auth_bypass_enabled():
            hosted_required = [
                'WORKSPACE_ROOT',
            ]

        # Sprites-specific requirements (only in hosted-sprites mode)
        hosted_sprites_required = hosted_required + [
            'SPRITES_TOKEN',  # API token for Sprites.dev
            'SPRITES_ORG',  # Organization ID for Sprites
            'SPRITES_TARGET_SPRITE',  # Workspace sprite to target
            'SPRITES_LOCAL_API_PORT',  # local_api port inside target sprite
        ]

        return {
            RunMode.LOCAL.value: {
                SandboxProvider.LOCAL.value: [
                    'WORKSPACE_ROOT',  # Required for all modes
                ],
                SandboxProvider.SANDBOX.value: [
                    'WORKSPACE_ROOT',
                ],
                SandboxProvider.SPRITES.value: [
                    'WORKSPACE_ROOT',
                    'SPRITES_TOKEN',
                    'SPRITES_ORG',
                ],
            },
            RunMode.HOSTED.value: {
                SandboxProvider.LOCAL.value: hosted_required,
                SandboxProvider.SANDBOX.value: hosted_required,
                SandboxProvider.SPRITES.value: hosted_sprites_required,
            },
        }

    def validate_startup(self) -> None:
        """Validate configuration at startup.

        Checks that required environment variables are set for the active mode and provider.
        Raises ValueError with actionable error message listing all missing variables.

        Note: WORKSPACE_ROOT check is skipped if workspace_root is already set in config.

        Raises:
            ValueError: If required env vars are missing or invalid
        """
        all_required_by_mode_provider = self._get_required_env_vars()
        required = all_required_by_mode_provider[self.run_mode.value][self.sandbox_provider.value]

        # Check required env vars, but skip WORKSPACE_ROOT if already configured
        missing = []
        for var in required:
            if var == 'WORKSPACE_ROOT' and self.workspace_root:
                # Skip WORKSPACE_ROOT check if workspace_root is already set
                continue
            if not os.environ.get(var):
                missing.append(var)

        if missing:
            mode_upper = self.run_mode.value.upper()
            provider_upper = self.sandbox_provider.value.upper()
            raise ValueError(
                f"Startup validation failed for {mode_upper} mode with {provider_upper} provider.\n"
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"\n"
                f"Configuration:\n"
                f"  Mode: {self.run_mode.value}\n"
                f"  Provider: {self.sandbox_provider.value}\n"
                f"  Workspace Root: {self.workspace_root}\n"
                f"\n"
                f"Required variables:\n"
                f"  {', '.join(required)}\n"
                f"\n"
                f"Set missing variables as environment variables and retry."
            )
