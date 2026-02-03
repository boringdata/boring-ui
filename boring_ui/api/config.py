"""Configuration for boring-ui API."""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class APIConfig:
    """Central configuration for all API routers.

    This dataclass is passed to all create_*_router() factories,
    enabling dependency injection and avoiding global state.
    """
    workspace_root: Path
    cors_origins: list[str] = field(default_factory=lambda: ['http://localhost:5173'])

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
