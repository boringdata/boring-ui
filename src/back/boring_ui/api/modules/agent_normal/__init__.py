"""agent-normal module for boring-ui API.

Owns runtime-only endpoints and delegates workspace/PTY side effects to the
service owners.
"""

from .router import create_agent_normal_router

__all__ = [
    "create_agent_normal_router",
]

