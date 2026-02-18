"""agent-normal module for boring-ui API.

This module owns runtime-only endpoints (session lifecycle) and delegates
workspace/PTY side effects to their owning services.
"""

from .router import create_agent_normal_router

__all__ = [
    "create_agent_normal_router",
]

