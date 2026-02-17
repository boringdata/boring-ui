"""Contract tests for route ownership dispatch table.

Validates that every route pattern in the Feature 3 design doc section 5.3
is correctly matched and routed to the expected plane.
"""

import pytest

from control_plane.app.routing.ownership import (
    Plane,
    ROUTE_TABLE,
    RouteMatch,
    resolve_owner,
)


class TestRouteTable:
    """Verify the dispatch table structure matches the design contract."""

    def test_table_is_nonempty(self):
        assert len(ROUTE_TABLE) > 0

    def test_all_entries_have_required_fields(self):
        for entry in ROUTE_TABLE:
            assert entry.pattern, f'Missing pattern: {entry}'
            assert isinstance(entry.plane, Plane), f'Bad plane: {entry}'
            assert entry.description, f'Missing description: {entry}'

    def test_control_plane_entries_are_not_proxied(self):
        for entry in ROUTE_TABLE:
            if entry.plane == Plane.CONTROL:
                assert not entry.proxied, (
                    f'Control plane route should not be proxied: {entry.pattern}'
                )

    def test_workspace_plane_entries_are_proxied(self):
        for entry in ROUTE_TABLE:
            if entry.plane == Plane.WORKSPACE:
                assert entry.proxied, (
                    f'Workspace plane route should be proxied: {entry.pattern}'
                )


class TestControlPlaneRoutes:
    """Section 5.3 control plane route ownership."""

    @pytest.mark.parametrize('path', [
        '/auth/login',
        '/auth/callback',
        '/auth/logout',
        '/auth/some/nested/path',
    ])
    def test_auth_routes_owned_by_control_plane(self, path):
        result = resolve_owner(path)
        assert result is not None, f'{path} should match'
        assert result.entry.plane == Plane.CONTROL
        assert result.workspace_id is None

    def test_app_config_owned_by_control_plane(self):
        result = resolve_owner('/api/v1/app-config')
        assert result is not None
        assert result.entry.plane == Plane.CONTROL
        assert result.workspace_id is None

    def test_me_endpoint_owned_by_control_plane(self):
        result = resolve_owner('/api/v1/me')
        assert result is not None
        assert result.entry.plane == Plane.CONTROL
        assert result.workspace_id is None

    @pytest.mark.parametrize('path', [
        '/api/v1/workspaces',
        '/api/v1/workspaces/ws_123',
        '/api/v1/workspaces/ws_123/members',
        '/api/v1/workspaces/ws_123/runtime',
        '/api/v1/workspaces/ws_123/retry',
        '/api/v1/workspaces/ws_123/shares',
        '/api/v1/workspaces/ws_123/members/m_456',
    ])
    def test_workspace_crud_routes_owned_by_control_plane(self, path):
        result = resolve_owner(path)
        assert result is not None, f'{path} should match'
        assert result.entry.plane == Plane.CONTROL

    def test_session_workspace_owned_by_control_plane(self):
        result = resolve_owner('/api/v1/session/workspace')
        assert result is not None
        assert result.entry.plane == Plane.CONTROL
        assert result.workspace_id is None


class TestWorkspacePlaneRoutes:
    """Section 5.3 workspace plane route ownership (proxied)."""

    @pytest.mark.parametrize('path,expected_ws_id', [
        ('/w/ws_123/app', 'ws_123'),
        ('/w/ws_123/app/index.html', 'ws_123'),
        ('/w/ws_abc/app/assets/main.js', 'ws_abc'),
    ])
    def test_app_routes_owned_by_workspace_plane(self, path, expected_ws_id):
        result = resolve_owner(path)
        assert result is not None, f'{path} should match'
        assert result.entry.plane == Plane.WORKSPACE
        assert result.entry.proxied is True
        assert result.workspace_id == expected_ws_id

    @pytest.mark.parametrize('path,expected_ws_id', [
        ('/w/ws_123/api/v1/files', 'ws_123'),
        ('/w/ws_123/api/v1/files/list', 'ws_123'),
    ])
    def test_file_routes_owned_by_workspace_plane(self, path, expected_ws_id):
        result = resolve_owner(path)
        assert result is not None, f'{path} should match'
        assert result.entry.plane == Plane.WORKSPACE
        assert result.workspace_id == expected_ws_id

    @pytest.mark.parametrize('path,expected_ws_id', [
        ('/w/ws_123/api/v1/git', 'ws_123'),
        ('/w/ws_123/api/v1/git/status', 'ws_123'),
        ('/w/ws_123/api/v1/git/diff', 'ws_123'),
    ])
    def test_git_routes_owned_by_workspace_plane(self, path, expected_ws_id):
        result = resolve_owner(path)
        assert result is not None, f'{path} should match'
        assert result.entry.plane == Plane.WORKSPACE
        assert result.workspace_id == expected_ws_id

    @pytest.mark.parametrize('path,expected_ws_id', [
        ('/w/ws_123/api/v1/pty', 'ws_123'),
        ('/w/ws_123/api/v1/pty/session_abc', 'ws_123'),
    ])
    def test_pty_routes_owned_by_workspace_plane(self, path, expected_ws_id):
        result = resolve_owner(path)
        assert result is not None, f'{path} should match'
        assert result.entry.plane == Plane.WORKSPACE
        assert result.workspace_id == expected_ws_id

    @pytest.mark.parametrize('path,expected_ws_id', [
        ('/w/ws_123/api/v1/agent/sessions', 'ws_123'),
        ('/w/ws_123/api/v1/agent/sessions/s_001/stream', 'ws_123'),
        ('/w/ws_123/api/v1/agent/sessions/s_001/input', 'ws_123'),
        ('/w/ws_123/api/v1/agent/sessions/s_001/stop', 'ws_123'),
    ])
    def test_agent_session_routes_owned_by_workspace_plane(self, path, expected_ws_id):
        result = resolve_owner(path)
        assert result is not None, f'{path} should match'
        assert result.entry.plane == Plane.WORKSPACE
        assert result.workspace_id == expected_ws_id


class TestUnmatchedRoutes:
    """Paths that don't match any entry should return None."""

    @pytest.mark.parametrize('path', [
        '/',
        '/health',
        '/api/v1/unknown',
        '/api/v1/workspaceships',
        '/api/v1/workspaceship/crew',
        '/random/path',
        '/w/',
        '/w/ws_123/application',
        '/w/ws_123/api/v1/filesystem',
        '/w/ws_123/api/v1/gitops',
        '/workspace/ws_123/app',
    ])
    def test_unmatched_paths_return_none(self, path):
        result = resolve_owner(path)
        assert result is None, f'{path} should not match any route'


class TestWorkspaceIdExtraction:
    """Verify workspace_id is correctly extracted from path patterns."""

    def test_extracts_simple_workspace_id(self):
        result = resolve_owner('/w/ws_123/api/v1/files')
        assert result is not None
        assert result.workspace_id == 'ws_123'

    def test_extracts_uuid_workspace_id(self):
        result = resolve_owner('/w/550e8400-e29b-41d4-a716-446655440000/api/v1/files')
        assert result is not None
        assert result.workspace_id == '550e8400-e29b-41d4-a716-446655440000'

    def test_extracts_alphanumeric_workspace_id(self):
        result = resolve_owner('/w/acme_workspace_42/app')
        assert result is not None
        assert result.workspace_id == 'acme_workspace_42'

    def test_control_plane_routes_have_no_workspace_id(self):
        result = resolve_owner('/api/v1/me')
        assert result is not None
        assert result.workspace_id is None


class TestRoutePrecedence:
    """Verify that more specific patterns match before broader ones."""

    def test_workspace_api_matches_before_app_wildcard(self):
        """``/w/{id}/api/v1/files`` should match files route, not app wildcard."""
        result = resolve_owner('/w/ws_123/api/v1/files/list')
        assert result is not None
        assert 'file' in result.entry.description.lower()
