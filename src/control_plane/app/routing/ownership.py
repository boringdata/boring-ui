"""Route ownership table and plane resolution.

Defines which plane (control or workspace) owns each route pattern,
matching the routing contract in the Feature 3 design doc section 5.3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


class Plane(Enum):
    """Identifies which plane serves a route."""

    CONTROL = 'control'
    WORKSPACE = 'workspace'


@dataclass(frozen=True, slots=True)
class RouteEntry:
    """A single row in the route ownership dispatch table.

    Args:
        pattern: URL path pattern (may contain {workspace_id} placeholder).
        plane: Which plane owns this route.
        description: Human-readable purpose for diagnostics.
        proxied: Whether the control plane proxies this to a workspace runtime.
    """

    pattern: str
    plane: Plane
    description: str
    proxied: bool = False


class RouteMatch(NamedTuple):
    """Result of resolving a request path against the ownership table."""

    entry: RouteEntry
    workspace_id: str | None


# ------------------------------------------------------------------
# Dispatch table — matches Feature 3 design doc section 5.3.
#
# Order matters: entries are evaluated top-to-bottom and the first
# match wins.  More specific patterns must precede broader ones.
# ------------------------------------------------------------------
ROUTE_TABLE: tuple[RouteEntry, ...] = (
    # --- Control plane routes ---
    RouteEntry(
        pattern='/auth/*',
        plane=Plane.CONTROL,
        description='Supabase login/callback/session setup',
    ),
    RouteEntry(
        pattern='/api/v1/app-config',
        plane=Plane.CONTROL,
        description='App branding/config by host and app_id',
    ),
    RouteEntry(
        pattern='/api/v1/me',
        plane=Plane.CONTROL,
        description='User/session info',
    ),
    RouteEntry(
        pattern='/api/v1/workspaces*',
        plane=Plane.CONTROL,
        description='Workspace CRUD/members/runtime status',
    ),
    RouteEntry(
        pattern='/api/v1/session/workspace',
        plane=Plane.CONTROL,
        description='Active workspace selection',
    ),
    # --- Workspace plane routes (proxied via control plane) ---
    RouteEntry(
        pattern='/w/{workspace_id}/app*',
        plane=Plane.WORKSPACE,
        description='Co-hosted frontend assets/pages',
        proxied=True,
    ),
    RouteEntry(
        pattern='/w/{workspace_id}/api/v1/files*',
        plane=Plane.WORKSPACE,
        description='File operations',
        proxied=True,
    ),
    RouteEntry(
        pattern='/w/{workspace_id}/api/v1/git*',
        plane=Plane.WORKSPACE,
        description='Git operations',
        proxied=True,
    ),
    RouteEntry(
        pattern='/w/{workspace_id}/api/v1/pty*',
        plane=Plane.WORKSPACE,
        description='Terminal/PTY',
        proxied=True,
    ),
    RouteEntry(
        pattern='/w/{workspace_id}/api/v1/agent/sessions*',
        plane=Plane.WORKSPACE,
        description='Agent stream/input/stop',
        proxied=True,
    ),
)


def _build_pattern_regex(pattern: str) -> re.Pattern[str]:
    """Build a regex for a dispatch table pattern.

    Handles three syntactic elements:
      - Literal path segments (escaped for regex safety).
      - ``{workspace_id}`` → named group matching a single path segment.
      - Trailing ``*`` → match any remaining characters.
    """
    parts: list[str] = []
    rest = pattern

    while rest:
        # Handle {workspace_id} placeholder.
        ws_start = rest.find('{workspace_id}')
        star_pos = rest.find('*')

        if ws_start >= 0 and (star_pos < 0 or ws_start < star_pos):
            # Literal before the placeholder.
            parts.append(re.escape(rest[:ws_start]))
            parts.append('(?P<workspace_id>[^/]+)')
            rest = rest[ws_start + len('{workspace_id}'):]
        elif star_pos >= 0:
            # We only support trailing '*' patterns in the dispatch table.
            if star_pos != len(rest) - 1:
                raise ValueError(f"Unsupported '*' placement in pattern: {pattern}")

            literal = rest[:star_pos]
            parts.append(re.escape(literal))

            # Segment-boundary wildcard:
            # - '/auth/*' keeps classic prefix semantics.
            # - '...workspaces*' and '.../app*' only match exact segment or nested path.
            if literal.endswith('/'):
                parts.append('.*')
            else:
                parts.append('(?:$|/.*)')
            rest = ''
        else:
            # Remaining literal.
            parts.append(re.escape(rest))
            rest = ''

    return re.compile('^' + ''.join(parts) + '$')


# Pre-compile regexes for each table entry.
_COMPILED_TABLE: list[tuple[re.Pattern[str], RouteEntry]] = [
    (_build_pattern_regex(entry.pattern), entry) for entry in ROUTE_TABLE
]


def resolve_owner(path: str) -> RouteMatch | None:
    """Resolve which plane owns the given request path.

    Args:
        path: The URL path to match (e.g. ``/api/v1/me`` or
              ``/w/ws_123/api/v1/files/list``).

    Returns:
        A ``RouteMatch`` with the matched entry and extracted workspace_id
        (if the route is workspace-scoped), or ``None`` if no entry matches.
    """
    for regex, entry in _COMPILED_TABLE:
        m = regex.match(path)
        if m:
            workspace_id = m.groupdict().get('workspace_id')
            return RouteMatch(entry=entry, workspace_id=workspace_id)
    return None
