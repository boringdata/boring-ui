"""Local API module - workspace-scoped file, git, and exec operations.

This module implements the workspace plane (`local-api`) for the two-module architecture (bd-1adh.2).
It provides internal-only endpoints for:
- File operations (list, read, write)
- Git operations (status, diff, log)
- Exec operations (command execution)

All operations are workspace-scoped to a configured workspace_root.
No end-user authentication is implemented; trust boundary is deployment topology.

See TWO_MODULE_API_LOCAL_API_PLAN.md for architecture details.
"""

from .app import create_local_api_app
from .router import create_local_api_router

__all__ = [
    "create_local_api_app",
    "create_local_api_router",
]
