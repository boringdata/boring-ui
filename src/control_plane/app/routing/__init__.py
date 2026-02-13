"""Route ownership and dispatch for control/workspace plane boundary."""

from .ownership import Plane, RouteEntry, ROUTE_TABLE, resolve_owner
from .context import WorkspaceContext, resolve_workspace_context
from .dispatcher import RouteDispatchMiddleware
from .proxy_security import (
    ProxyHeaderConfig,
    ProxySecurityError,
    build_proxy_config,
    redact_response_headers,
    sanitize_proxy_headers,
)

__all__ = [
    'Plane',
    'ProxyHeaderConfig',
    'ProxySecurityError',
    'RouteEntry',
    'ROUTE_TABLE',
    'RouteDispatchMiddleware',
    'WorkspaceContext',
    'build_proxy_config',
    'redact_response_headers',
    'resolve_owner',
    'resolve_workspace_context',
    'sanitize_proxy_headers',
]
