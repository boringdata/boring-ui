"""Git module for boring-ui API.

Provides git operations: status, diff, show.
"""
from .router import create_git_router
from .service import GitService

__all__ = [
    'create_git_router',
    'GitService',
]
