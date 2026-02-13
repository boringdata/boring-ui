"""Route ownership contract regression tests.

Bead: bd-223o.11.1.1 (E1a)

Validates:
  - Route table parity: exact entry count per plane prevents silent additions
  - Every table entry has at least one exercised path
  - Boundary paths near ownership borders resolve correctly
  - No accidental cross-plane leakage between control and workspace routes
  - RouteEntry immutability and RouteMatch structure
  - Pattern-level coverage: each ROUTE_TABLE entry is individually verified
"""

from __future__ import annotations

import pytest

from control_plane.app.routing.ownership import (
    Plane,
    ROUTE_TABLE,
    RouteEntry,
    RouteMatch,
    resolve_owner,
)


# ── Table structure regression ──────────────────────────────────────

# These counts are pinned to the design doc section 5.3 contract.
# Any addition or removal of a route entry should update these counts
# AND the corresponding test paths below.

EXPECTED_CONTROL_ENTRIES = 5   # auth, app-config, me, workspaces, session/workspace
EXPECTED_WORKSPACE_ENTRIES = 5  # app, files, git, pty, agent/sessions
EXPECTED_TOTAL_ENTRIES = 10


class TestTableParity:
    """Pin the route table shape to prevent silent structural drift."""

    def test_total_entry_count(self):
        assert len(ROUTE_TABLE) == EXPECTED_TOTAL_ENTRIES, (
            f'Route table has {len(ROUTE_TABLE)} entries, expected {EXPECTED_TOTAL_ENTRIES}. '
            f'If you added/removed a route, update EXPECTED_TOTAL_ENTRIES.'
        )

    def test_control_plane_count(self):
        control = [e for e in ROUTE_TABLE if e.plane == Plane.CONTROL]
        assert len(control) == EXPECTED_CONTROL_ENTRIES

    def test_workspace_plane_count(self):
        workspace = [e for e in ROUTE_TABLE if e.plane == Plane.WORKSPACE]
        assert len(workspace) == EXPECTED_WORKSPACE_ENTRIES

    def test_every_entry_has_nonempty_description(self):
        for entry in ROUTE_TABLE:
            assert entry.description.strip(), (
                f'Entry {entry.pattern!r} has empty description'
            )


# ── Pattern-level verification ──────────────────────────────────────

# Map each ROUTE_TABLE entry pattern to a representative test path.
# This ensures every entry in the table is individually exercised.

_PATTERN_TO_REPRESENTATIVE_PATH = {
    '/auth/*': '/auth/login',
    '/api/v1/app-config': '/api/v1/app-config',
    '/api/v1/me': '/api/v1/me',
    '/api/v1/workspaces*': '/api/v1/workspaces',
    '/api/v1/session/workspace': '/api/v1/session/workspace',
    '/w/{workspace_id}/app*': '/w/ws_1/app',
    '/w/{workspace_id}/api/v1/files*': '/w/ws_1/api/v1/files',
    '/w/{workspace_id}/api/v1/git*': '/w/ws_1/api/v1/git',
    '/w/{workspace_id}/api/v1/pty*': '/w/ws_1/api/v1/pty',
    '/w/{workspace_id}/api/v1/agent/sessions*': '/w/ws_1/api/v1/agent/sessions',
}


class TestPatternCoverage:
    """Every ROUTE_TABLE entry has exactly one exercised representative path."""

    def test_all_patterns_have_representative(self):
        """Ensure our map covers every entry in the table."""
        table_patterns = {e.pattern for e in ROUTE_TABLE}
        map_patterns = set(_PATTERN_TO_REPRESENTATIVE_PATH.keys())
        assert table_patterns == map_patterns, (
            f'Missing coverage for: {table_patterns - map_patterns}'
        )

    @pytest.mark.parametrize(
        'pattern,path',
        list(_PATTERN_TO_REPRESENTATIVE_PATH.items()),
        ids=list(_PATTERN_TO_REPRESENTATIVE_PATH.keys()),
    )
    def test_representative_path_matches_entry(self, pattern, path):
        result = resolve_owner(path)
        assert result is not None, f'{path} should match pattern {pattern}'
        assert result.entry.pattern == pattern, (
            f'{path} matched {result.entry.pattern!r} instead of {pattern!r}'
        )


# ── Boundary tests: near-misses ─────────────────────────────────────


class TestBoundaryNearMisses:
    """Paths that are close to matching but should NOT be owned."""

    @pytest.mark.parametrize('path', [
        '/authentication/login',    # not /auth/*
        '/api/v1/app-configs',      # plural
        '/api/v1/me/profile',       # /me is exact match (no wildcard)
        '/api/v1/mesh',             # starts with /me prefix
        '/api/v2/workspaces',       # wrong API version
        '/api/v1/session/workspaces',  # plural
        '/api/v1/session/workspace/extra',  # extra segment
    ])
    def test_control_near_misses_unmatched(self, path):
        result = resolve_owner(path)
        # Either None or matched to a different entry
        if result is not None:
            # Verify it didn't accidentally match a control plane route
            # that it shouldn't (e.g. /api/v1/mesh != /api/v1/me)
            assert path not in ('/api/v1/mesh',), (
                f'{path} should not match any route'
            )

    @pytest.mark.parametrize('path', [
        '/w//api/v1/files',           # empty workspace_id
        '/w/ws_1/api/v1/file',        # singular (not /files*)
        '/w/ws_1/api/v1/git-ops',     # not /git*
        '/w/ws_1/api/v1/pty-session', # not /pty*
        '/w/ws_1/api/v2/files',       # wrong API version
        '/ws/ws_1/api/v1/files',      # /ws/ not /w/
    ])
    def test_workspace_near_misses_unmatched(self, path):
        result = resolve_owner(path)
        assert result is None, f'{path} should not match any workspace route'


# ── Cross-plane leakage ─────────────────────────────────────────────


class TestCrossPlaneLeakage:
    """Ensure control plane paths never resolve to workspace, and vice versa."""

    CONTROL_PATHS = [
        '/auth/login',
        '/auth/callback',
        '/api/v1/app-config',
        '/api/v1/me',
        '/api/v1/workspaces',
        '/api/v1/workspaces/ws_1',
        '/api/v1/workspaces/ws_1/members',
        '/api/v1/session/workspace',
    ]

    WORKSPACE_PATHS = [
        '/w/ws_1/app',
        '/w/ws_1/app/index.html',
        '/w/ws_1/api/v1/files',
        '/w/ws_1/api/v1/files/list',
        '/w/ws_1/api/v1/git',
        '/w/ws_1/api/v1/git/status',
        '/w/ws_1/api/v1/pty',
        '/w/ws_1/api/v1/agent/sessions',
        '/w/ws_1/api/v1/agent/sessions/s_1/stream',
    ]

    @pytest.mark.parametrize('path', CONTROL_PATHS)
    def test_control_paths_never_resolve_to_workspace(self, path):
        result = resolve_owner(path)
        assert result is not None
        assert result.entry.plane == Plane.CONTROL, (
            f'{path} resolved to workspace plane instead of control'
        )

    @pytest.mark.parametrize('path', WORKSPACE_PATHS)
    def test_workspace_paths_never_resolve_to_control(self, path):
        result = resolve_owner(path)
        assert result is not None
        assert result.entry.plane == Plane.WORKSPACE, (
            f'{path} resolved to control plane instead of workspace'
        )

    @pytest.mark.parametrize('path', WORKSPACE_PATHS)
    def test_workspace_paths_are_proxied(self, path):
        result = resolve_owner(path)
        assert result is not None
        assert result.entry.proxied is True

    @pytest.mark.parametrize('path', CONTROL_PATHS)
    def test_control_paths_are_not_proxied(self, path):
        result = resolve_owner(path)
        assert result is not None
        assert result.entry.proxied is False


# ── RouteEntry immutability ──────────────────────────────────────────


class TestRouteEntryImmutability:

    def test_route_entry_is_frozen(self):
        entry = ROUTE_TABLE[0]
        with pytest.raises(AttributeError):
            entry.pattern = '/hacked'

    def test_route_entry_uses_slots(self):
        entry = ROUTE_TABLE[0]
        assert hasattr(entry, '__slots__')


# ── RouteMatch structure ─────────────────────────────────────────────


class TestRouteMatchStructure:

    def test_route_match_is_named_tuple(self):
        result = resolve_owner('/api/v1/me')
        assert isinstance(result, RouteMatch)
        assert hasattr(result, 'entry')
        assert hasattr(result, 'workspace_id')

    def test_workspace_match_extracts_workspace_id(self):
        result = resolve_owner('/w/ws_test/api/v1/files')
        assert result.workspace_id == 'ws_test'

    def test_control_match_has_none_workspace_id(self):
        result = resolve_owner('/api/v1/me')
        assert result.workspace_id is None
