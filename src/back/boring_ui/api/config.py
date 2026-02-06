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
