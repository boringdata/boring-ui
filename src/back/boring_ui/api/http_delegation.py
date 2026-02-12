"""HTTP route delegation for sandbox mode.

Routes file/search/git/session HTTP requests through the workspace
service proxy when running in sandbox mode, preserving existing
request/response contracts.

Delegation pattern:
  1. Check if sandbox mode is active
  2. Forward request to workspace service via SpritesProxyClient
  3. Return response with same status/headers/body as upstream
  4. Normalize errors to browser-safe responses

This module provides pure delegation logic decoupled from the router
framework. Each delegator function takes a request description and
returns a response description, letting the caller handle framework
integration.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import quote, urlencode

from .error_normalization import normalize_http_error, error_response_body

logger = logging.getLogger(__name__)


class DelegationMethod(Enum):
    """HTTP methods supported for delegation."""
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    PATCH = 'PATCH'


@dataclass(frozen=True)
class DelegationRequest:
    """A request to delegate to the workspace service."""
    method: DelegationMethod
    path: str
    query_params: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    json_body: dict | list | None = None
    content: bytes | None = None

    @property
    def full_path(self) -> str:
        """Build the full path with query string."""
        if not self.query_params:
            return self.path
        qs = urlencode(self.query_params, quote_via=quote)
        return f'{self.path}?{qs}'


@dataclass(frozen=True)
class DelegationResponse:
    """Response from a delegated request."""
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b''
    json_body: dict | list | None = None

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400


class DelegationError(Exception):
    """Raised when delegation fails at the transport level."""
    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ── File route delegators ──


def delegate_list_tree(path: str = '.') -> DelegationRequest:
    """Build delegation request for GET /api/tree."""
    return DelegationRequest(
        method=DelegationMethod.GET,
        path='/api/tree',
        query_params={'path': path},
    )


def delegate_read_file(path: str) -> DelegationRequest:
    """Build delegation request for GET /api/file."""
    return DelegationRequest(
        method=DelegationMethod.GET,
        path='/api/file',
        query_params={'path': path},
    )


def delegate_write_file(path: str, content: str) -> DelegationRequest:
    """Build delegation request for PUT /api/file."""
    return DelegationRequest(
        method=DelegationMethod.PUT,
        path='/api/file',
        query_params={'path': path},
        json_body={'content': content},
    )


def delegate_delete_file(path: str) -> DelegationRequest:
    """Build delegation request for DELETE /api/file."""
    return DelegationRequest(
        method=DelegationMethod.DELETE,
        path='/api/file',
        query_params={'path': path},
    )


def delegate_rename_file(old_path: str, new_path: str) -> DelegationRequest:
    """Build delegation request for POST /api/file/rename."""
    return DelegationRequest(
        method=DelegationMethod.POST,
        path='/api/file/rename',
        json_body={'old_path': old_path, 'new_path': new_path},
    )


def delegate_move_file(src_path: str, dest_dir: str) -> DelegationRequest:
    """Build delegation request for POST /api/file/move."""
    return DelegationRequest(
        method=DelegationMethod.POST,
        path='/api/file/move',
        json_body={'src_path': src_path, 'dest_dir': dest_dir},
    )


def delegate_search_files(pattern: str, path: str = '.') -> DelegationRequest:
    """Build delegation request for GET /api/search."""
    return DelegationRequest(
        method=DelegationMethod.GET,
        path='/api/search',
        query_params={'q': pattern, 'path': path},
    )


# ── Git route delegators ──


def delegate_git_status() -> DelegationRequest:
    """Build delegation request for GET /api/git/status."""
    return DelegationRequest(
        method=DelegationMethod.GET,
        path='/api/git/status',
    )


def delegate_git_diff(path: str) -> DelegationRequest:
    """Build delegation request for GET /api/git/diff."""
    return DelegationRequest(
        method=DelegationMethod.GET,
        path='/api/git/diff',
        query_params={'path': path},
    )


def delegate_git_show(path: str) -> DelegationRequest:
    """Build delegation request for GET /api/git/show."""
    return DelegationRequest(
        method=DelegationMethod.GET,
        path='/api/git/show',
        query_params={'path': path},
    )


# ── Error mapping ──


def map_upstream_status(status_code: int) -> DelegationResponse:
    """Map an upstream error status to a safe delegation response.

    Used when the proxy client returns an error status from the
    workspace service. Maps to browser-safe error bodies.
    """
    if status_code < 400:
        return DelegationResponse(status_code=status_code)

    # Map upstream status to normalized error
    status_map = {
        400: 'bad_request',
        403: 'unauthorized',
        404: 'not_found',
        409: 'conflict',
        422: 'validation_error',
        429: 'rate_limited',
    }

    if status_code in status_map:
        error_key = status_map[status_code]
    elif status_code >= 500:
        error_key = 'provider_error'
    else:
        error_key = 'internal_error'

    normalized = normalize_http_error(error_key)
    body = error_response_body(normalized)

    import json
    return DelegationResponse(
        status_code=normalized.http_status,
        headers={'content-type': 'application/json'},
        body=json.dumps(body).encode('utf-8'),
        json_body=body,
    )


# ── Delegation registry ──


# Maps (method, path_prefix) -> delegator description
DELEGATION_ROUTES: dict[tuple[str, str], str] = {
    ('GET', '/api/tree'): 'list_tree',
    ('GET', '/api/file'): 'read_file',
    ('PUT', '/api/file'): 'write_file',
    ('DELETE', '/api/file'): 'delete_file',
    ('POST', '/api/file/rename'): 'rename_file',
    ('POST', '/api/file/move'): 'move_file',
    ('GET', '/api/search'): 'search_files',
    ('GET', '/api/git/status'): 'git_status',
    ('GET', '/api/git/diff'): 'git_diff',
    ('GET', '/api/git/show'): 'git_show',
}


def is_delegatable(method: str, path: str) -> bool:
    """Check if a request method+path is delegatable in sandbox mode."""
    return (method.upper(), path) in DELEGATION_ROUTES


def list_delegatable_routes() -> list[tuple[str, str, str]]:
    """List all delegatable routes as (method, path, description) tuples."""
    return [
        (method, path, desc)
        for (method, path), desc in sorted(DELEGATION_ROUTES.items())
    ]
