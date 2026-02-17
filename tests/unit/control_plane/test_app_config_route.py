"""Integration tests for GET /api/v1/app-config.

Bead: bd-223o.8.2 (I2)

Tests:
  - Valid host → 200 with full branding payload
  - Unknown host (no mapping, no default) → 404
  - Mapped host but no config registered → 404
  - Wildcard fallback → 200
  - Default fallback → 200
  - Response payload matches design doc contract
  - Port in Host header is stripped
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from control_plane.app.identity.resolver import AppConfig, AppIdentityResolver
from control_plane.app.routes.app_config import create_app_config_router

# ── Fixtures ──────────────────────────────────────────────────────────

BORING_CONFIG = AppConfig(
    app_id='boring-ui',
    name='Boring UI',
    logo='/assets/boring-ui-logo.svg',
    default_release_id='2026-02-13.1',
)


def _build_app(
    host_map: dict[str, str],
    app_configs: dict[str, AppConfig] | None = None,
    default_app_id: str | None = None,
) -> FastAPI:
    resolver = AppIdentityResolver(
        host_map=host_map,
        app_configs=app_configs,
        default_app_id=default_app_id,
    )
    app = FastAPI()
    app.include_router(create_app_config_router(resolver))
    return app


# =====================================================================
# Happy path
# =====================================================================


class TestAppConfigHappyPath:
    @pytest.mark.asyncio
    async def test_returns_200_with_full_payload(self):
        app = _build_app(
            host_map={'boring-ui.example.com': 'boring-ui'},
            app_configs={'boring-ui': BORING_CONFIG},
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(
                '/api/v1/app-config',
                headers={'host': 'boring-ui.example.com'},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body['app_id'] == 'boring-ui'
            assert body['name'] == 'Boring UI'
            assert body['logo'] == '/assets/boring-ui-logo.svg'
            assert body['default_release_id'] == '2026-02-13.1'

    @pytest.mark.asyncio
    async def test_response_has_exactly_four_fields(self):
        app = _build_app(
            host_map={'*': 'boring-ui'},
            app_configs={'boring-ui': BORING_CONFIG},
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get('/api/v1/app-config')
            body = resp.json()
            assert set(body.keys()) == {
                'app_id', 'name', 'logo', 'default_release_id',
            }

    @pytest.mark.asyncio
    async def test_port_in_host_is_stripped(self):
        app = _build_app(
            host_map={'localhost': 'boring-ui'},
            app_configs={'boring-ui': BORING_CONFIG},
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(
                '/api/v1/app-config',
                headers={'host': 'localhost:5173'},
            )
            assert resp.status_code == 200
            assert resp.json()['app_id'] == 'boring-ui'


# =====================================================================
# Wildcard and default fallbacks
# =====================================================================


class TestAppConfigFallbacks:
    @pytest.mark.asyncio
    async def test_wildcard_fallback(self):
        app = _build_app(
            host_map={'*': 'boring-ui'},
            app_configs={'boring-ui': BORING_CONFIG},
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(
                '/api/v1/app-config',
                headers={'host': 'anything.example.com'},
            )
            assert resp.status_code == 200
            assert resp.json()['app_id'] == 'boring-ui'

    @pytest.mark.asyncio
    async def test_default_app_id_fallback(self):
        app = _build_app(
            host_map={},
            app_configs={'boring-ui': BORING_CONFIG},
            default_app_id='boring-ui',
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(
                '/api/v1/app-config',
                headers={'host': 'unknown.example.com'},
            )
            assert resp.status_code == 200
            assert resp.json()['app_id'] == 'boring-ui'


# =====================================================================
# Error cases
# =====================================================================


class TestAppConfigErrors:
    @pytest.mark.asyncio
    async def test_unknown_host_returns_404(self):
        app = _build_app(host_map={})
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(
                '/api/v1/app-config',
                headers={'host': 'unknown.example.com'},
            )
            assert resp.status_code == 404
            body = resp.json()
            assert body['error'] == 'app_config_not_found'

    @pytest.mark.asyncio
    async def test_mapped_host_but_no_config_returns_404(self):
        app = _build_app(
            host_map={'example.com': 'orphan-app'},
            app_configs={},  # No config for orphan-app.
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp = await client.get(
                '/api/v1/app-config',
                headers={'host': 'example.com'},
            )
            assert resp.status_code == 404
            body = resp.json()
            assert body['error'] == 'app_config_not_found'
            assert 'orphan-app' in body['detail']


# =====================================================================
# Multi-app
# =====================================================================


class TestAppConfigMultiApp:
    @pytest.mark.asyncio
    async def test_different_hosts_return_different_configs(self):
        acme_config = AppConfig(
            app_id='acme', name='Acme', logo='/acme.svg',
            default_release_id='1.0.0',
        )
        app = _build_app(
            host_map={
                'boring.example.com': 'boring-ui',
                'acme.example.com': 'acme',
            },
            app_configs={
                'boring-ui': BORING_CONFIG,
                'acme': acme_config,
            },
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url='http://test'
        ) as client:
            resp_boring = await client.get(
                '/api/v1/app-config',
                headers={'host': 'boring.example.com'},
            )
            resp_acme = await client.get(
                '/api/v1/app-config',
                headers={'host': 'acme.example.com'},
            )

            assert resp_boring.json()['app_id'] == 'boring-ui'
            assert resp_acme.json()['app_id'] == 'acme'
            assert resp_boring.json()['name'] != resp_acme.json()['name']
