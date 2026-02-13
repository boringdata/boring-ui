"""Negative tests for app context mismatch scenarios.

Bead: bd-223o.8.3.1 (I3a)

Validates:
  - Mismatch via different host→app_id against workspace app_id
  - Mismatch across workspace-scoped path patterns
  - Consistent 400 error code and payload structure
  - Multiple workspace routes all reject on mismatch
  - Wildcard/default resolution producing mismatch
  - Empty string app_id edge cases
  - Session-level context (middleware sets state from different sources)
  - Error payload always includes both resolved and workspace app_ids
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from control_plane.app.identity.app_context import (
    AppContextMiddleware,
    AppContextMismatch,
    validate_app_context,
)


# ── Helpers ──────────────────────────────────────────────────────────


class _InjectContextMiddleware(BaseHTTPMiddleware):
    """Injects app_id and workspace_app_id from per-request header overrides.

    Simulates different resolution sources (host header, path extraction,
    session lookup) by allowing tests to set values via custom headers:
      X-Test-App-Id: resolved app_id (from host resolver)
      X-Test-Workspace-App-Id: workspace's stored app_id
    """

    def __init__(self, app, default_app_id=None, default_ws_app_id=None):
        super().__init__(app)
        self._default_app_id = default_app_id
        self._default_ws_app_id = default_ws_app_id

    async def dispatch(self, request, call_next):
        app_id = request.headers.get(
            'x-test-app-id', self._default_app_id,
        )
        ws_app_id = request.headers.get(
            'x-test-workspace-app-id', self._default_ws_app_id,
        )
        if app_id is not None:
            request.state.app_id = app_id
        if ws_app_id is not None:
            request.state.workspace_app_id = ws_app_id
        return await call_next(request)


def _build_multi_route_app(
    default_app_id=None,
    default_ws_app_id=None,
) -> FastAPI:
    """Build an app with multiple workspace-scoped routes for testing."""
    app = FastAPI()

    app.add_middleware(AppContextMiddleware)
    app.add_middleware(
        _InjectContextMiddleware,
        default_app_id=default_app_id,
        default_ws_app_id=default_ws_app_id,
    )

    @app.get('/w/{ws_id}/api/v1/files')
    async def list_files(ws_id: str):
        return {'route': 'files', 'workspace_id': ws_id}

    @app.get('/w/{ws_id}/api/v1/agent/sessions')
    async def list_sessions(ws_id: str):
        return {'route': 'sessions', 'workspace_id': ws_id}

    @app.post('/w/{ws_id}/api/v1/agent/sessions')
    async def create_session(ws_id: str):
        return {'route': 'create_session', 'workspace_id': ws_id}

    @app.get('/w/{ws_id}/api/v1/settings')
    async def workspace_settings(ws_id: str):
        return {'route': 'settings', 'workspace_id': ws_id}

    @app.get('/api/v1/me')
    async def me():
        return {'route': 'me'}

    @app.get('/api/v1/workspaces')
    async def list_workspaces():
        return {'route': 'workspaces'}

    return app


# =====================================================================
# 1. Host-resolved mismatch across routes
# =====================================================================


class TestHostResolvedMismatch:
    """Simulate host→app_id resolving to a different app than workspace."""

    @pytest.mark.asyncio
    async def test_mismatch_on_files_route(self):
        app = _build_multi_route_app(
            default_app_id='app-from-host',
            default_ws_app_id='workspace-stored-app',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get('/w/ws_1/api/v1/files')
            assert r.status_code == 400
            body = r.json()
            assert body['error'] == 'app_context_mismatch'

    @pytest.mark.asyncio
    async def test_mismatch_on_sessions_route(self):
        app = _build_multi_route_app(
            default_app_id='app-from-host',
            default_ws_app_id='workspace-stored-app',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 400
            assert r.json()['error'] == 'app_context_mismatch'

    @pytest.mark.asyncio
    async def test_mismatch_on_create_session_route(self):
        app = _build_multi_route_app(
            default_app_id='app-from-host',
            default_ws_app_id='workspace-stored-app',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.post('/w/ws_1/api/v1/agent/sessions')
            assert r.status_code == 400
            assert r.json()['error'] == 'app_context_mismatch'

    @pytest.mark.asyncio
    async def test_mismatch_on_settings_route(self):
        app = _build_multi_route_app(
            default_app_id='app-from-host',
            default_ws_app_id='workspace-stored-app',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get('/w/ws_1/api/v1/settings')
            assert r.status_code == 400
            assert r.json()['error'] == 'app_context_mismatch'


# =====================================================================
# 2. Consistent error payload structure
# =====================================================================


class TestErrorPayloadConsistency:
    """Verify 400 app_context_mismatch payloads always have both app_ids."""

    @pytest.mark.asyncio
    async def test_payload_includes_resolved_app_id(self):
        app = _build_multi_route_app(
            default_app_id='resolved-one',
            default_ws_app_id='stored-two',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get('/w/ws_1/api/v1/files')
            body = r.json()
            assert body['resolved_app_id'] == 'resolved-one'
            assert body['workspace_app_id'] == 'stored-two'

    @pytest.mark.asyncio
    async def test_payload_keys_are_stable(self):
        """Error response must have exactly these three keys."""
        app = _build_multi_route_app(
            default_app_id='a', default_ws_app_id='b',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get('/w/ws_1/api/v1/files')
            body = r.json()
            assert set(body.keys()) == {
                'error', 'resolved_app_id', 'workspace_app_id',
            }

    @pytest.mark.asyncio
    async def test_error_code_is_always_app_context_mismatch(self):
        """The error code must be exactly 'app_context_mismatch'."""
        app = _build_multi_route_app(
            default_app_id='foo', default_ws_app_id='bar',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            for path in [
                '/w/ws_1/api/v1/files',
                '/w/ws_1/api/v1/agent/sessions',
                '/w/ws_1/api/v1/settings',
            ]:
                r = await client.get(path)
                assert r.status_code == 400
                assert r.json()['error'] == 'app_context_mismatch'


# =====================================================================
# 3. Per-request header override mismatch (simulating dynamic contexts)
# =====================================================================


class TestDynamicContextMismatch:
    """Simulate scenarios where resolution source varies per request."""

    @pytest.mark.asyncio
    async def test_header_override_creates_mismatch(self):
        """Even when defaults match, header override can introduce mismatch."""
        app = _build_multi_route_app(
            default_app_id='boring-ui',
            default_ws_app_id='boring-ui',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            # Defaults match — should pass.
            r = await client.get('/w/ws_1/api/v1/files')
            assert r.status_code == 200

            # Override resolved app_id via header — creates mismatch.
            r = await client.get(
                '/w/ws_1/api/v1/files',
                headers={'x-test-app-id': 'rogue-app'},
            )
            assert r.status_code == 400
            assert r.json()['resolved_app_id'] == 'rogue-app'

    @pytest.mark.asyncio
    async def test_header_override_workspace_app_id(self):
        """Override workspace_app_id to simulate wrong workspace lookup."""
        app = _build_multi_route_app(
            default_app_id='boring-ui',
            default_ws_app_id='boring-ui',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get(
                '/w/ws_1/api/v1/files',
                headers={'x-test-workspace-app-id': 'different-app'},
            )
            assert r.status_code == 400
            assert r.json()['workspace_app_id'] == 'different-app'

    @pytest.mark.asyncio
    async def test_both_overrides_matching_passes(self):
        """When both overrides agree, request passes."""
        app = _build_multi_route_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get(
                '/w/ws_1/api/v1/files',
                headers={
                    'x-test-app-id': 'custom-app',
                    'x-test-workspace-app-id': 'custom-app',
                },
            )
            assert r.status_code == 200


# =====================================================================
# 4. Non-workspace routes unaffected by mismatch
# =====================================================================


class TestNonWorkspaceRoutesUnaffected:
    """Verify mismatch middleware does not block non-workspace routes."""

    @pytest.mark.asyncio
    async def test_me_route_passes_despite_app_id_set(self):
        """Non-workspace routes with resolved app_id but no workspace pass."""
        app = _build_multi_route_app(
            default_app_id='boring-ui',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get('/api/v1/me')
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_workspaces_list_passes(self):
        app = _build_multi_route_app(
            default_app_id='boring-ui',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            r = await client.get('/api/v1/workspaces')
            assert r.status_code == 200


# =====================================================================
# 5. Edge cases: empty string and case sensitivity
# =====================================================================


class TestEdgeCases:

    def test_empty_string_vs_none(self):
        """Empty string is a valid app_id and should mismatch against a
        non-empty workspace app_id."""
        with pytest.raises(AppContextMismatch):
            validate_app_context('', 'boring-ui')

    def test_case_sensitive_mismatch(self):
        """App IDs are case-sensitive: 'Boring-UI' != 'boring-ui'."""
        with pytest.raises(AppContextMismatch):
            validate_app_context('Boring-UI', 'boring-ui')

    def test_whitespace_not_stripped(self):
        """Whitespace differences should cause mismatch."""
        with pytest.raises(AppContextMismatch):
            validate_app_context(' boring-ui', 'boring-ui')

    def test_same_prefix_different_suffix(self):
        """Partial matches don't count."""
        with pytest.raises(AppContextMismatch):
            validate_app_context('boring-ui-v2', 'boring-ui')

    def test_empty_string_vs_empty_string_matches(self):
        """Two empty strings should match (no-op case)."""
        validate_app_context('', '')  # Should not raise.


# =====================================================================
# 6. Exception details carry correct values
# =====================================================================


class TestExceptionDetails:

    def test_exception_preserves_resolved_app_id(self):
        try:
            validate_app_context('host-app', 'ws-app')
        except AppContextMismatch as exc:
            assert exc.resolved_app_id == 'host-app'
        else:
            pytest.fail('Expected AppContextMismatch')

    def test_exception_preserves_workspace_app_id(self):
        try:
            validate_app_context('host-app', 'ws-app')
        except AppContextMismatch as exc:
            assert exc.workspace_app_id == 'ws-app'
        else:
            pytest.fail('Expected AppContextMismatch')

    def test_exception_message_format(self):
        try:
            validate_app_context('alpha', 'beta')
        except AppContextMismatch as exc:
            msg = str(exc)
            assert 'alpha' in msg
            assert 'beta' in msg
        else:
            pytest.fail('Expected AppContextMismatch')

    def test_exception_is_subclass_of_exception(self):
        exc = AppContextMismatch('a', 'b')
        assert isinstance(exc, Exception)


# =====================================================================
# 7. Multiple workspace IDs same mismatch
# =====================================================================


class TestMultiWorkspaceMismatch:
    """Ensure mismatch is app-level, not workspace-ID-level."""

    @pytest.mark.asyncio
    async def test_different_workspace_ids_same_mismatch(self):
        """Mismatch applies regardless of which workspace_id is in the URL."""
        app = _build_multi_route_app(
            default_app_id='app-a',
            default_ws_app_id='app-b',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            for ws_id in ['ws_1', 'ws_2', 'ws_999']:
                r = await client.get(f'/w/{ws_id}/api/v1/files')
                assert r.status_code == 400
                assert r.json()['error'] == 'app_context_mismatch'
