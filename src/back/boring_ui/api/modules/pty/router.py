"""PTY WebSocket router for boring-ui API."""
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from ...config import APIConfig
from ...policy import enforce_delegated_policy_ws_reason_or_none
from .service import PTYService, SharedSession, _SERVICE


# Use the singleton service instance from service.py
_pty_service = _SERVICE


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

        normalized_session_id: str | None = None
        if session_id is not None:
            candidate = str(session_id).strip()
            if candidate:
                try:
                    normalized_session_id = str(uuid.UUID(candidate))
                except (ValueError, AttributeError, TypeError):
                    await websocket.close(code=4004, reason="Invalid session_id (must be a UUID)")
                    return

        deny_reason = enforce_delegated_policy_ws_reason_or_none(
            websocket.headers,
            {"pty.session.attach"} if normalized_session_id else {"pty.session.start"},
            operation=("pty-service.ws.attach" if normalized_session_id else "pty-service.ws.start"),
            require_session_id=normalized_session_id is not None,
            expected_session_id=normalized_session_id,
        )
        if deny_reason is not None:
            await websocket.close(code=4004, reason=deny_reason)
            return

        # Get or create session
        try:
            session, is_new = await _pty_service.get_or_create_session(
                session_id=normalized_session_id,
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
