"""Local API: Private workspace-plane for file, git, and PTY operations.

This module contains handlers for operations on the local workspace filesystem.
It's designed to run either in-process (LOCAL mode) or remotely via Sprites proxy
(HOSTED mode with Sprites provider).

Module structure:
- files: File CRUD operations (read, write, delete, rename, move)
- git: Git operations (status, diff, show)
- exec: PTY/shell operations

All handlers use capability token authorization in hosted mode.
Workspace isolation is enforced via path validation.
"""

from .files import create_files_router
from .git import create_git_router
from .exec import create_exec_router
from .app import create_local_api_app
from .router import create_local_api_router

__all__ = [
    'create_files_router',
    'create_git_router',
    'create_exec_router',
    'create_local_api_app',
    'create_local_api_router',
]
