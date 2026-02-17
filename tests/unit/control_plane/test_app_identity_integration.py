"""Cross-cutting integration tests for app identity, config, context, and branding.

Bead: bd-1zm6 (I5)

Exercises the full app-identity pipeline end-to-end:
  - Host resolution → /api/v1/app-config → branding chain round-trip
  - Multi-app host isolation: different hosts → different app_ids → different configs
  - Host resolver feeds app-config route feeds branding chain (no component gap)
  - App context mismatch enforcement through resolver + middleware
  - Multi-tenancy: workspace filtering by resolved app_id
  - Resolver ↔ branding chain agreement: config from resolver matches branding input
  - Deterministic round-trip: same host always produces same config + branding
  - Full pipeline negative: unknown host propagates through config and context
  - Cross-app workspace access blocked by context middleware with resolver
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from control_plane.app.identity.app_context import AppContextMiddleware
from control_plane.app.identity.branding import (
    LoginBranding,
    WorkspaceBranding,
    resolve_login_branding,
)
from control_plane.app.identity.resolver import (
    AppConfig,
    AppIdentityResolver,
)
from control_plane.app.routes.app_config import create_app_config_router


# ── Shared configs ─────────────────────────────────────────────────

BORING_CONFIG = AppConfig(
    app_id='boring-ui',
    name='Boring UI',
    logo='/assets/boring-ui-logo.svg',
    default_release_id='2026-02-13.1',
)

ACME_CONFIG = AppConfig(
    app_id='acme-app',
    name='Acme Corp',
    logo='/assets/acme-logo.png',
    default_release_id='2026-01-01.1',
)

MULTI_APP_HOST_MAP = {
    'boring.example.com': 'boring-ui',
    'acme.example.com': 'acme-app',
    'localhost': 'boring-ui',
}

MULTI_APP_CONFIGS = {
    'boring-ui': BORING_CONFIG,
    'acme-app': ACME_CONFIG,
}


@pytest.fixture
def resolver():
    return AppIdentityResolver(
        host_map=MULTI_APP_HOST_MAP,
        app_configs=MULTI_APP_CONFIGS,
    )


# ── Middleware that wires resolver into request.state ──────────────


class _ResolverMiddleware(BaseHTTPMiddleware):
    """Runs host resolution and injects app_id into request.state."""

    def __init__(self, app, resolver: AppIdentityResolver):
        super().__init__(app)
        self._resolver = resolver

    async def dispatch(self, request, call_next):
        host = request.headers.get('host', '')
        try:
            resolution = self._resolver.resolve(host)
            request.state.app_id = resolution.app_id
            request.state.app_config = resolution.config
        except KeyError:
            request.state.app_id = None
            request.state.app_config = None
        return await call_next(request)


class _WorkspaceLookupMiddleware(BaseHTTPMiddleware):
    """Simulates workspace lookup that sets workspace_app_id on state.

    Uses a static mapping of workspace_id → app_id for testing.
    """

    def __init__(self, app, workspace_apps: dict[str, str]):
        super().__init__(app)
        self._workspace_apps = workspace_apps

    async def dispatch(self, request, call_next):
        # Extract workspace_id from path if present.
        path = request.url.path
        if path.startswith('/w/'):
            parts = path.split('/')
            if len(parts) >= 3:
                ws_id = parts[2]
                app_id = self._workspace_apps.get(ws_id)
                if app_id is not None:
                    request.state.workspace_app_id = app_id
        return await call_next(request)


def _build_full_pipeline_app(
    resolver: AppIdentityResolver,
    workspace_apps: dict[str, str] | None = None,
) -> FastAPI:
    """Build a FastAPI app with the full identity pipeline wired."""
    app = FastAPI()

    # Routes.
    app.include_router(create_app_config_router(resolver))

    @app.get('/w/{ws_id}/api/v1/files')
    async def list_files(ws_id: str):
        return {'workspace_id': ws_id, 'route': 'files'}

    @app.get('/w/{ws_id}/api/v1/sessions')
    async def list_sessions(ws_id: str):
        return {'workspace_id': ws_id, 'route': 'sessions'}

    @app.get('/api/v1/me')
    async def me():
        return {'user': 'test-user'}

    @app.get('/api/v1/branding')
    async def branding(request: Request):
        config = getattr(request.state, 'app_config', None)
        result = resolve_login_branding(app_config=config)
        return {
            'name': result.name,
            'logo': result.logo,
            'source': result.source,
        }

    # Middleware (inner → outer ordering in add_middleware).
    app.add_middleware(AppContextMiddleware)
    app.add_middleware(
        _WorkspaceLookupMiddleware,
        workspace_apps=workspace_apps or {},
    )
    app.add_middleware(_ResolverMiddleware, resolver=resolver)

    return app


# =====================================================================
# 1. Host → app-config round-trip
# =====================================================================


class TestHostToAppConfigRoundTrip:
    """Full pipeline: Host header → resolver → /api/v1/app-config response."""

    @pytest.mark.asyncio
    async def test_boring_host_returns_boring_config(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/app-config',
                headers={'host': 'boring.example.com'},
            )
            assert r.status_code == 200
            body = r.json()
            assert body['app_id'] == 'boring-ui'
            assert body['name'] == 'Boring UI'
            assert body['default_release_id'] == '2026-02-13.1'

    @pytest.mark.asyncio
    async def test_acme_host_returns_acme_config(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/app-config',
                headers={'host': 'acme.example.com'},
            )
            assert r.status_code == 200
            body = r.json()
            assert body['app_id'] == 'acme-app'
            assert body['name'] == 'Acme Corp'
            assert body['default_release_id'] == '2026-01-01.1'

    @pytest.mark.asyncio
    async def test_unknown_host_returns_404(self):
        resolver = AppIdentityResolver(
            host_map={'known.example.com': 'boring-ui'},
            app_configs={'boring-ui': BORING_CONFIG},
        )
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/app-config',
                headers={'host': 'unknown.example.com'},
            )
            assert r.status_code == 404
            assert r.json()['error'] == 'app_config_not_found'

    @pytest.mark.asyncio
    async def test_localhost_with_port_resolves(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/app-config',
                headers={'host': 'localhost:5173'},
            )
            assert r.status_code == 200
            assert r.json()['app_id'] == 'boring-ui'


# =====================================================================
# 2. Multi-app host isolation
# =====================================================================


class TestMultiAppHostIsolation:
    """Different hosts resolve to different apps with isolated configs."""

    @pytest.mark.asyncio
    async def test_same_request_path_different_host_different_config(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            boring_resp = await c.get(
                '/api/v1/app-config',
                headers={'host': 'boring.example.com'},
            )
            acme_resp = await c.get(
                '/api/v1/app-config',
                headers={'host': 'acme.example.com'},
            )
            assert boring_resp.json()['app_id'] != acme_resp.json()['app_id']
            assert boring_resp.json()['logo'] != acme_resp.json()['logo']
            assert boring_resp.json()['name'] != acme_resp.json()['name']

    @pytest.mark.asyncio
    async def test_sequential_requests_no_cross_contamination(self, resolver):
        """Rapid sequential requests with alternating hosts stay isolated."""
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            for _ in range(5):
                b = await c.get(
                    '/api/v1/app-config',
                    headers={'host': 'boring.example.com'},
                )
                a = await c.get(
                    '/api/v1/app-config',
                    headers={'host': 'acme.example.com'},
                )
                assert b.json()['app_id'] == 'boring-ui'
                assert a.json()['app_id'] == 'acme-app'


# =====================================================================
# 3. Resolver → branding chain agreement
# =====================================================================


class TestResolverBrandingAgreement:
    """Config from resolver produces correct branding via branding chain."""

    @pytest.mark.asyncio
    async def test_boring_branding_from_resolver(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/branding',
                headers={'host': 'boring.example.com'},
            )
            assert r.status_code == 200
            body = r.json()
            assert body['name'] == 'Boring UI'
            assert body['logo'] == '/assets/boring-ui-logo.svg'
            assert body['source'] == 'app'

    @pytest.mark.asyncio
    async def test_acme_branding_from_resolver(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/branding',
                headers={'host': 'acme.example.com'},
            )
            assert r.status_code == 200
            body = r.json()
            assert body['name'] == 'Acme Corp'
            assert body['logo'] == '/assets/acme-logo.png'
            assert body['source'] == 'app'

    @pytest.mark.asyncio
    async def test_unknown_host_falls_to_default_branding(self):
        resolver = AppIdentityResolver(host_map={})
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/branding',
                headers={'host': 'unknown.example.com'},
            )
            assert r.status_code == 200
            body = r.json()
            assert body['name'] == 'App'
            assert body['source'] == 'default'

    def test_resolver_config_feeds_branding_directly(self, resolver):
        """Verify resolver output is compatible branding chain input."""
        resolution = resolver.resolve('boring.example.com')
        branding = resolve_login_branding(app_config=resolution.config)
        assert branding.name == 'Boring UI'
        assert branding.logo == '/assets/boring-ui-logo.svg'
        assert branding.source == 'app'

    def test_workspace_branding_overrides_resolver_config(self, resolver):
        """Workspace branding takes precedence over resolver-provided config."""
        resolution = resolver.resolve('boring.example.com')
        ws = WorkspaceBranding(name='Custom Portal', logo='/custom.svg')
        branding = resolve_login_branding(
            workspace_branding=ws,
            app_config=resolution.config,
        )
        assert branding.name == 'Custom Portal'
        assert branding.logo == '/custom.svg'
        assert branding.source == 'workspace'


# =====================================================================
# 4. Context mismatch via resolver + middleware
# =====================================================================


class TestContextMismatchWithResolver:
    """Full pipeline: resolver sets app_id, workspace lookup sets workspace_app_id,
    mismatch middleware blocks the request."""

    @pytest.mark.asyncio
    async def test_matching_app_allows_workspace_access(self, resolver):
        workspace_apps = {'ws_boring_1': 'boring-ui'}
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/w/ws_boring_1/api/v1/files',
                headers={'host': 'boring.example.com'},
            )
            assert r.status_code == 200
            assert r.json()['workspace_id'] == 'ws_boring_1'

    @pytest.mark.asyncio
    async def test_cross_app_workspace_blocked(self, resolver):
        """Accessing a boring-ui workspace from acme host is blocked."""
        workspace_apps = {'ws_boring_1': 'boring-ui'}
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/w/ws_boring_1/api/v1/files',
                headers={'host': 'acme.example.com'},
            )
            assert r.status_code == 400
            body = r.json()
            assert body['error'] == 'app_context_mismatch'
            assert body['resolved_app_id'] == 'acme-app'
            assert body['workspace_app_id'] == 'boring-ui'

    @pytest.mark.asyncio
    async def test_reverse_cross_app_also_blocked(self, resolver):
        """Accessing an acme workspace from boring host is also blocked."""
        workspace_apps = {'ws_acme_1': 'acme-app'}
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/w/ws_acme_1/api/v1/files',
                headers={'host': 'boring.example.com'},
            )
            assert r.status_code == 400
            body = r.json()
            assert body['error'] == 'app_context_mismatch'
            assert body['resolved_app_id'] == 'boring-ui'
            assert body['workspace_app_id'] == 'acme-app'

    @pytest.mark.asyncio
    async def test_non_workspace_routes_unblocked_with_resolver(self, resolver):
        """Non-workspace routes pass even when resolver resolves an app_id."""
        workspace_apps = {'ws_boring_1': 'boring-ui'}
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/api/v1/me',
                headers={'host': 'boring.example.com'},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_workspace_passes_through(self, resolver):
        """Workspace not in lookup table → no workspace_app_id → no mismatch."""
        app = _build_full_pipeline_app(resolver, workspace_apps={})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            r = await c.get(
                '/w/ws_unknown/api/v1/files',
                headers={'host': 'boring.example.com'},
            )
            assert r.status_code == 200


# =====================================================================
# 5. Multi-tenancy workspace routing
# =====================================================================


class TestMultiTenancyWorkspaceRouting:
    """User accessing workspaces from correct host succeeds; wrong host fails."""

    @pytest.mark.asyncio
    async def test_user_accesses_own_app_workspaces(self, resolver):
        """Both apps' workspaces accessible from their respective hosts."""
        workspace_apps = {
            'ws_boring_1': 'boring-ui',
            'ws_boring_2': 'boring-ui',
            'ws_acme_1': 'acme-app',
        }
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            # Boring host → boring workspaces: OK
            for ws in ['ws_boring_1', 'ws_boring_2']:
                r = await c.get(
                    f'/w/{ws}/api/v1/files',
                    headers={'host': 'boring.example.com'},
                )
                assert r.status_code == 200, f'{ws} should be accessible'

            # Acme host → acme workspace: OK
            r = await c.get(
                '/w/ws_acme_1/api/v1/files',
                headers={'host': 'acme.example.com'},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_cross_app_access_all_blocked(self, resolver):
        """Every combination of wrong host + workspace is blocked."""
        workspace_apps = {
            'ws_boring_1': 'boring-ui',
            'ws_acme_1': 'acme-app',
        }
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            # Boring workspace from acme host: blocked
            r = await c.get(
                '/w/ws_boring_1/api/v1/files',
                headers={'host': 'acme.example.com'},
            )
            assert r.status_code == 400

            # Acme workspace from boring host: blocked
            r = await c.get(
                '/w/ws_acme_1/api/v1/files',
                headers={'host': 'boring.example.com'},
            )
            assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_mismatch_on_multiple_workspace_routes(self, resolver):
        """Mismatch is enforced on all workspace-scoped route patterns."""
        workspace_apps = {'ws_acme_1': 'acme-app'}
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            for path in [
                '/w/ws_acme_1/api/v1/files',
                '/w/ws_acme_1/api/v1/sessions',
            ]:
                r = await c.get(
                    path,
                    headers={'host': 'boring.example.com'},
                )
                assert r.status_code == 400, f'{path} should be blocked'
                assert r.json()['error'] == 'app_context_mismatch'


# =====================================================================
# 6. Deterministic round-trip consistency
# =====================================================================


class TestDeterministicRoundTrip:
    """Same host always produces the same config and branding."""

    @pytest.mark.asyncio
    async def test_repeated_config_requests_identical(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            responses = []
            for _ in range(10):
                r = await c.get(
                    '/api/v1/app-config',
                    headers={'host': 'boring.example.com'},
                )
                responses.append(r.json())
            # All 10 responses must be identical.
            assert all(r == responses[0] for r in responses)

    @pytest.mark.asyncio
    async def test_repeated_branding_requests_identical(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            responses = []
            for _ in range(10):
                r = await c.get(
                    '/api/v1/branding',
                    headers={'host': 'acme.example.com'},
                )
                responses.append(r.json())
            assert all(r == responses[0] for r in responses)

    def test_resolver_is_deterministic(self, resolver):
        """Multiple calls to resolver.resolve() return identical results."""
        results = [resolver.resolve('boring.example.com') for _ in range(20)]
        assert all(r == results[0] for r in results)


# =====================================================================
# 7. Config ↔ branding field agreement
# =====================================================================


class TestConfigBrandingFieldAgreement:
    """AppConfig fields used by branding chain match route response fields."""

    @pytest.mark.asyncio
    async def test_config_name_matches_branding_name(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            config_r = await c.get(
                '/api/v1/app-config',
                headers={'host': 'boring.example.com'},
            )
            branding_r = await c.get(
                '/api/v1/branding',
                headers={'host': 'boring.example.com'},
            )
            assert config_r.json()['name'] == branding_r.json()['name']

    @pytest.mark.asyncio
    async def test_config_logo_matches_branding_logo(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            config_r = await c.get(
                '/api/v1/app-config',
                headers={'host': 'acme.example.com'},
            )
            branding_r = await c.get(
                '/api/v1/branding',
                headers={'host': 'acme.example.com'},
            )
            assert config_r.json()['logo'] == branding_r.json()['logo']

    @pytest.mark.asyncio
    async def test_both_apps_have_distinct_branding(self, resolver):
        app = _build_full_pipeline_app(resolver)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            boring = await c.get(
                '/api/v1/branding',
                headers={'host': 'boring.example.com'},
            )
            acme = await c.get(
                '/api/v1/branding',
                headers={'host': 'acme.example.com'},
            )
            assert boring.json()['name'] != acme.json()['name']
            assert boring.json()['logo'] != acme.json()['logo']


# =====================================================================
# 8. Full pipeline negative paths
# =====================================================================


class TestFullPipelineNegative:
    """End-to-end negative scenarios through the full stack."""

    @pytest.mark.asyncio
    async def test_config_404_does_not_break_workspace_routes(self):
        """Config 404 on unknown host should not affect workspace routing."""
        resolver = AppIdentityResolver(
            host_map={'known.example.com': 'boring-ui'},
            app_configs={'boring-ui': BORING_CONFIG},
        )
        workspace_apps = {'ws_1': 'boring-ui'}
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            # Config for unknown host: 404
            r = await c.get(
                '/api/v1/app-config',
                headers={'host': 'unknown.example.com'},
            )
            assert r.status_code == 404

            # Known host workspace access still works fine.
            r = await c.get(
                '/w/ws_1/api/v1/files',
                headers={'host': 'known.example.com'},
            )
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_wildcard_resolver_allows_all_hosts(self):
        """Wildcard resolver accepts any host for config and workspaces."""
        resolver = AppIdentityResolver(
            host_map={'*': 'boring-ui'},
            app_configs={'boring-ui': BORING_CONFIG},
        )
        workspace_apps = {'ws_1': 'boring-ui'}
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            for host in ['random.com', 'anything.dev', 'localhost:9000']:
                r = await c.get(
                    '/api/v1/app-config',
                    headers={'host': host},
                )
                assert r.status_code == 200
                assert r.json()['app_id'] == 'boring-ui'

                r = await c.get(
                    '/w/ws_1/api/v1/files',
                    headers={'host': host},
                )
                assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_app_without_config_still_enforces_mismatch(self):
        """App resolved but no config registered: context mismatch still works."""
        resolver = AppIdentityResolver(
            host_map={
                'app-a.com': 'app-a',
                'app-b.com': 'app-b',
            },
            # No configs registered — resolver returns config=None.
        )
        workspace_apps = {'ws_a': 'app-a'}
        app = _build_full_pipeline_app(resolver, workspace_apps)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as c:
            # Correct host → passes (no mismatch).
            r = await c.get(
                '/w/ws_a/api/v1/files',
                headers={'host': 'app-a.com'},
            )
            assert r.status_code == 200

            # Wrong host → mismatch even without config.
            r = await c.get(
                '/w/ws_a/api/v1/files',
                headers={'host': 'app-b.com'},
            )
            assert r.status_code == 400
            assert r.json()['error'] == 'app_context_mismatch'
