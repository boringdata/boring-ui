"""PTY WebSocket router for boring-ui API."""
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from ...config import APIConfig
from .service import PTYService, SharedSession


# Global service instance
_pty_service = PTYService()


def create_pty_router(config: APIConfig) -> APIRouter:
    """Create PTY WebSocket router.

    Args:
        config: API configuration with pty_providers

    Returns:
        FastAPI router with /pty WebSocket endpoint
    """
    router = APIRouter(tags=['pty'])

    @router.websocket('/pty')
    async def pty_websocket(
        websocket: WebSocket,
        session_id: str | None = Query(None),
        provider: str = Query('shell'),
    ):
        """WebSocket endpoint for PTY connections.

        Args:
            session_id: Optional session ID to reconnect to existing session
            provider: Provider name (must be in config.pty_providers)
        """
        # Start cleanup task if not running
        await _pty_service.ensure_cleanup_running()

        # Validate provider
        if provider not in config.pty_providers:
            await websocket.close(
                code=4003,
                reason=f'Unknown provider: {provider}. Available: {list(config.pty_providers.keys())}'
            )
            return

        command = config.pty_providers[provider]

        # Get or create session
        try:
            session, is_new = await _pty_service.get_or_create_session(
                session_id=session_id,
                command=command,
                cwd=config.workspace_root,
            )
        except ValueError as e:
            await websocket.close(code=4004, reason=str(e))
            return

        # Accept WebSocket
        await websocket.accept()
        await session.add_client(websocket)

        try:
            # Message loop
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)

                    msg_type = message.get('type')

                    if msg_type == 'input':
                        session.write(message.get('data', ''))
                    elif msg_type == 'resize':
                        rows = message.get('rows', 24)
                        cols = message.get('cols', 80)
                        session.resize(rows, cols)
                    elif msg_type == 'ping':
                        await websocket.send_json({'type': 'pong'})

                except json.JSONDecodeError:
                    # Treat raw text as input
                    session.write(data)

        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            await session.remove_client(websocket)

    return router


def get_pty_service() -> PTYService:
    """Get the global PTY service instance."""
    return _pty_service
