"""Internal workspace service API contract.

This module defines the exact API surface that the control plane expects
from the workspace service running inside a sprite. It is the single
source of truth for:

  1. Endpoint paths and request/response shapes
  2. X-Workspace-API-Version header semantics
  3. Compatible version ranges
  4. Error mapping rules from upstream to browser-facing responses

Clients (SpritesServicesClient, SpritesProxyClient) and startup checks
(bd-ptl.1.2.4) use these definitions to validate workspace service
conformance.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Version Contract ──


WORKSPACE_API_VERSION_HEADER = 'X-Workspace-API-Version'
CURRENT_VERSION = '0.1.0'
MIN_COMPATIBLE_VERSION = '0.1.0'


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse a semver string into (major, minor, patch) tuple."""
    parts = version_str.strip().split('.')
    if len(parts) != 3:
        raise ValueError(f'Invalid version format: {version_str!r} (expected major.minor.patch)')
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        raise ValueError(f'Non-numeric version components in: {version_str!r}')


def is_compatible(upstream_version: str) -> bool:
    """Check if an upstream workspace service version is compatible.

    Compatibility rules (v0):
    - Major version must match exactly (breaking changes)
    - Minor version must be >= minimum (additive features)
    - Patch version is ignored (bug fixes only)
    """
    try:
        current = parse_version(upstream_version)
        minimum = parse_version(MIN_COMPATIBLE_VERSION)
    except ValueError:
        return False
    # Major must match
    if current[0] != minimum[0]:
        return False
    # Minor must be >= minimum
    if current[1] < minimum[1]:
        return False
    return True


# ── Healthz Contract ──


HEALTHZ_ENDPOINT = '/healthz'
VERSION_ENDPOINT = '/__meta/version'


@dataclass(frozen=True)
class HealthzResponse:
    """Expected shape of workspace service health check."""
    status: str  # "ok" or "degraded"
    version: str  # workspace API version


@dataclass(frozen=True)
class VersionResponse:
    """Expected shape of workspace service version endpoint."""
    version: str
    compatible_from: str


# ── Internal Auth Contract ──


INTERNAL_AUTH_HEADER = 'X-Workspace-Internal-Auth'


# ── Endpoint Contracts ──
# These mirror browser-facing routes but are the internal upstream versions.


@dataclass(frozen=True)
class EndpointContract:
    """Specification for a single internal API endpoint."""
    method: str
    path: str
    description: str
    required_headers: tuple[str, ...] = ()
    query_params: tuple[str, ...] = ()
    request_content_type: str | None = None
    success_status: int = 200
    error_statuses: tuple[int, ...] = (400, 404, 500)


# File operations (proxied from /api/*)
FILE_TREE = EndpointContract(
    method='GET',
    path='/api/tree',
    description='List directory contents',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
    query_params=('path',),
)

FILE_READ = EndpointContract(
    method='GET',
    path='/api/file',
    description='Read file contents',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
    query_params=('path',),
    error_statuses=(400, 404, 500),
)

FILE_WRITE = EndpointContract(
    method='PUT',
    path='/api/file',
    description='Write file contents',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
    query_params=('path',),
    request_content_type='application/json',
    error_statuses=(400, 422, 500),
)

FILE_DELETE = EndpointContract(
    method='DELETE',
    path='/api/file',
    description='Delete file or directory',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
    query_params=('path',),
    error_statuses=(400, 404, 500),
)

FILE_RENAME = EndpointContract(
    method='POST',
    path='/api/file/rename',
    description='Rename file or directory',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
    request_content_type='application/json',
    error_statuses=(400, 404, 409, 500),
)

FILE_MOVE = EndpointContract(
    method='POST',
    path='/api/file/move',
    description='Move file to another directory',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
    request_content_type='application/json',
    error_statuses=(400, 404, 500),
)

FILE_SEARCH = EndpointContract(
    method='GET',
    path='/api/search',
    description='Search files by pattern',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
    query_params=('q', 'path'),
    error_statuses=(400, 422, 500),
)

# Git operations
GIT_STATUS = EndpointContract(
    method='GET',
    path='/api/git/status',
    description='Git repository status',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
)

GIT_DIFF = EndpointContract(
    method='GET',
    path='/api/git/diff',
    description='Git diff for file',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
    query_params=('path',),
    error_statuses=(400, 500),
)

GIT_SHOW = EndpointContract(
    method='GET',
    path='/api/git/show',
    description='Show file at HEAD',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
    query_params=('path',),
    error_statuses=(400, 500),
)

# Session operations
SESSIONS_LIST = EndpointContract(
    method='GET',
    path='/api/sessions',
    description='List active sessions',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
)

SESSIONS_CREATE = EndpointContract(
    method='POST',
    path='/api/sessions',
    description='Create new session ID',
    required_headers=(INTERNAL_AUTH_HEADER, WORKSPACE_API_VERSION_HEADER),
)

# Health/meta (no auth required)
HEALTHZ = EndpointContract(
    method='GET',
    path=HEALTHZ_ENDPOINT,
    description='Health check',
    required_headers=(WORKSPACE_API_VERSION_HEADER,),
)

META_VERSION = EndpointContract(
    method='GET',
    path=VERSION_ENDPOINT,
    description='Version and compatibility info',
    required_headers=(),
)


# ── All Proxied Endpoints ──
# These are the endpoints that SpritesProxyClient forwards to.

PROXIED_ENDPOINTS: tuple[EndpointContract, ...] = (
    FILE_TREE, FILE_READ, FILE_WRITE, FILE_DELETE,
    FILE_RENAME, FILE_MOVE, FILE_SEARCH,
    GIT_STATUS, GIT_DIFF, GIT_SHOW,
    SESSIONS_LIST, SESSIONS_CREATE,
)

ALL_ENDPOINTS: tuple[EndpointContract, ...] = (
    *PROXIED_ENDPOINTS, HEALTHZ, META_VERSION,
)


# ── Error Mapping ──
# Maps upstream workspace service errors to browser-facing responses.


@dataclass(frozen=True)
class ErrorMapping:
    """Maps an upstream error condition to a browser-facing response."""
    upstream_status: int | str  # int for HTTP status, str for special conditions
    browser_status: int
    browser_detail: str
    log_level: str = 'warning'


# Upstream workspace service errors -> browser-visible errors
ERROR_MAPPINGS: tuple[ErrorMapping, ...] = (
    # Pass through standard errors
    ErrorMapping(400, 400, 'Bad request'),
    ErrorMapping(404, 404, 'Not found'),
    ErrorMapping(409, 409, 'Conflict'),
    ErrorMapping(422, 422, 'Validation error'),
    # Map upstream server errors to generic 502
    ErrorMapping(500, 502, 'Workspace service error'),
    ErrorMapping(502, 502, 'Workspace service unavailable'),
    ErrorMapping(503, 503, 'Workspace service temporarily unavailable'),
    # Map transport/connectivity failures
    ErrorMapping('connection_refused', 503, 'Workspace service unreachable'),
    ErrorMapping('connection_timeout', 504, 'Workspace service timeout'),
    ErrorMapping('read_timeout', 504, 'Workspace service response timeout'),
    ErrorMapping('version_mismatch', 502, 'Workspace service version incompatible'),
)


def map_upstream_error(upstream_status: int) -> tuple[int, str]:
    """Map an upstream HTTP status to a browser-facing (status, detail) pair.

    Returns the mapped status and a safe detail message. Raw upstream
    error bodies are never forwarded to the browser.
    """
    for mapping in ERROR_MAPPINGS:
        if mapping.upstream_status == upstream_status:
            return mapping.browser_status, mapping.browser_detail
    # Default: generic gateway error
    if upstream_status >= 500:
        return 502, 'Workspace service error'
    if upstream_status >= 400:
        return upstream_status, 'Upstream error'
    return 502, 'Unexpected upstream response'


# ── Validation Fixtures ──
# Used by SpritesServicesClient and startup health checks.


@dataclass(frozen=True)
class ValidationFixture:
    """A test fixture for validating workspace service conformance."""
    name: str
    endpoint: EndpointContract
    expected_status: int
    expected_keys: tuple[str, ...] = ()
    description: str = ''


HEALTH_CHECK_FIXTURES: tuple[ValidationFixture, ...] = (
    ValidationFixture(
        name='healthz_ok',
        endpoint=HEALTHZ,
        expected_status=200,
        expected_keys=('status',),
        description='Workspace service health endpoint returns status',
    ),
    ValidationFixture(
        name='version_ok',
        endpoint=META_VERSION,
        expected_status=200,
        expected_keys=('version',),
        description='Version endpoint returns API version',
    ),
)

SMOKE_CHECK_FIXTURES: tuple[ValidationFixture, ...] = (
    ValidationFixture(
        name='tree_root',
        endpoint=FILE_TREE,
        expected_status=200,
        expected_keys=('entries', 'path'),
        description='File tree returns entries for workspace root',
    ),
    ValidationFixture(
        name='git_status',
        endpoint=GIT_STATUS,
        expected_status=200,
        expected_keys=('is_repo',),
        description='Git status returns repository info',
    ),
    ValidationFixture(
        name='sessions_list',
        endpoint=SESSIONS_LIST,
        expected_status=200,
        expected_keys=('sessions',),
        description='Sessions list returns session array',
    ),
)

ALL_FIXTURES: tuple[ValidationFixture, ...] = (
    *HEALTH_CHECK_FIXTURES, *SMOKE_CHECK_FIXTURES,
)
