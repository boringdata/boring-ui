"""Utility routes: health, config, project, session, and metrics.

Bead: bd-20u3.6

Extracted from app.py to keep create_app as a thin orchestrator.
These routes are always mounted and don't depend on mode or feature flags.
"""

from fastapi import APIRouter
from starlette.responses import Response

from boring_ui.observability.metrics import metrics_text


def create_utility_router(config, enabled_features=None) -> APIRouter:
    """Create router with health, config, project, session, and metrics endpoints.

    Args:
        config: APIConfig instance with workspace_root and pty_providers.
        enabled_features: Optional dict of enabled feature flags for /health response.

    Returns:
        APIRouter with utility endpoints mounted.
    """
    router = APIRouter()

    @router.get('/health')
    async def health():
        """Health check endpoint."""
        result = {
            'status': 'ok',
            'workspace': str(config.workspace_root),
        }
        if enabled_features is not None:
            result['features'] = enabled_features
        return result

    @router.get('/api/config')
    async def get_config():
        """Get API configuration info."""
        return {
            'workspace_root': str(config.workspace_root),
            'pty_providers': list(config.pty_providers.keys()),
            'paths': {
                'files': '.',
            },
        }

    @router.get('/api/project')
    async def get_project():
        """Get project root for the frontend."""
        return {
            'root': str(config.workspace_root),
        }

    @router.get('/api/sessions')
    async def list_sessions():
        """List active PTY and stream sessions."""
        from .modules.stream import get_session_registry as get_stream_registry
        from .modules.pty import get_session_registry as get_pty_registry

        pty_sessions = [
            {
                'id': session_id,
                'type': 'pty',
                'alive': session.is_alive(),
                'clients': len(session.clients),
                'history_count': len(session.history),
            }
            for session_id, session in get_pty_registry().items()
        ]
        stream_sessions = [
            {
                'id': session_id,
                'type': 'stream',
                'alive': session.is_alive(),
                'clients': len(session.clients),
                'history_count': len(session.history),
            }
            for session_id, session in get_stream_registry().items()
        ]
        return {'sessions': pty_sessions + stream_sessions}

    @router.post('/api/sessions')
    async def create_session():
        """Create a new session ID (client will connect via WebSocket)."""
        import uuid
        return {'session_id': str(uuid.uuid4())}

    @router.get('/metrics')
    async def prometheus_metrics():
        """Prometheus metrics exposition endpoint."""
        body, content_type = metrics_text()
        return Response(content=body, media_type=content_type)

    return router
