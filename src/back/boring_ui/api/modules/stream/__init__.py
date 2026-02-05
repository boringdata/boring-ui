"""Stream module for boring-ui API.

Provides Claude stream WebSocket functionality for chat interfaces.
"""
from .router import create_stream_router, handle_stream_websocket
from .service import (
    StreamSession,
    build_stream_args,
    get_session_registry,
    MAX_HISTORY_LINES,
    IDLE_TTL_SECONDS,
    MAX_SESSIONS,
    DEFAULT_SLASH_COMMANDS,
)

__all__ = [
    'create_stream_router',
    'handle_stream_websocket',
    'StreamSession',
    'build_stream_args',
    'get_session_registry',
    'MAX_HISTORY_LINES',
    'IDLE_TTL_SECONDS',
    'MAX_SESSIONS',
    'DEFAULT_SLASH_COMMANDS',
]
