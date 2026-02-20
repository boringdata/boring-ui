"""Backward-compatible import for git router.

This module preserves the historical import path:
`boring_ui.api.git_routes`.
"""

from .modules.git import create_git_router

__all__ = ["create_git_router"]
