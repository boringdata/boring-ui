"""PTY module for boring-ui API.

Provides PTY WebSocket functionality for terminal connections.
"""
from .router import create_pty_router, get_pty_service
from .service import (
    PTYSession,
    SharedSession,
    PTYService,
    get_session_registry,
    PTY_HISTORY_BYTES,
    PTY_IDLE_TTL,
    PTY_MAX_SESSIONS,
)

__all__ = [
    'create_pty_router',
    'get_pty_service',
    'PTYSession',
    'SharedSession',
    'PTYService',
    'get_session_registry',
    'PTY_HISTORY_BYTES',
    'PTY_IDLE_TTL',
    'PTY_MAX_SESSIONS',
]
