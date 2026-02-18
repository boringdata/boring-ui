"""Configuration for boring-ui API."""
import os
from dataclasses import dataclass, field
from pathlib import Path


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


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a bool environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _workspace_plugin_allowlist() -> list[str]:
    """Parse optional comma-separated workspace plugin allowlist."""
    raw = os.environ.get('WORKSPACE_PLUGIN_ALLOWLIST', '')
    return [item.strip() for item in raw.split(',') if item.strip()]


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
    companion_url: str | None = field(
        default_factory=lambda: os.environ.get('COMPANION_URL')
    )
    pi_url: str | None = field(
        default_factory=lambda: os.environ.get('PI_URL')
    )
    # PI provider rendering mode:
    # - embedded: use built-in chat UI (functional fallback/default)
    # - iframe: render configured PI_URL inside iframe
    pi_mode: str = field(
        default_factory=lambda: (os.environ.get('PI_MODE') or 'embedded').strip().lower()
    )
    # Disabled by default because workspace plugins execute local Python modules.
    workspace_plugins_enabled: bool = field(
        default_factory=lambda: _env_bool('WORKSPACE_PLUGINS_ENABLED', False)
    )
    workspace_plugin_allowlist: list[str] = field(
        default_factory=_workspace_plugin_allowlist
    )
    # Off by default: exposes internal architecture/contract hints via /api/capabilities.
    # Enable explicitly in trusted environments only.
    capabilities_include_contract_metadata: bool = field(
        default_factory=lambda: _env_bool("CAPABILITIES_INCLUDE_CONTRACT_METADATA", False)
    )

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
