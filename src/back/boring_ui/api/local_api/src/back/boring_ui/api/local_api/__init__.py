"""Local API: Private workspace-plane for file, git, and PTY operations.

This module contains workspace-scoped handlers for:
- File operations (CRUD)
- Git operations (status, diff, show)
- PTY/exec operations (shell sessions)

All handlers are designed for both LOCAL (in-process) and HOSTED (remote) modes.
Imports are relative to the parent api package for backward compatibility.
"""

# Backward compatibility: re-export routers that were moved here
from .file_routes import create_file_router
from .git_routes import create_git_router
from .pty_bridge import create_pty_router

__all__ = [
    'create_file_router',
    'create_git_router',
    'create_pty_router',
]
