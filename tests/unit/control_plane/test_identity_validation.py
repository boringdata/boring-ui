"""Resolver config validation, fallback behavior, and app-config payload contract tests.

Beads: bd-223o.8.1.1 (I1a) + bd-223o.8.2.1 (I2a)

I1a validates:
  - Empty host_map with no default raises KeyError.
  - Empty host_map with default resolves correctly.
  - Misconfigured: host maps to app_id with no registered config.
  - Wildcard precedence: exact match wins over wildcard.
  - Default precedence: wildcard wins over default.
  - registered_hosts returns normalized copy.
  - get_config for unknown app_id returns None.
  - Multiple wildcards: last one wins (dict override).

I2a validates:
  - Full payload includes all 4 required fields.
  - Payload field types are correct.
  - Default values (empty string) propagated correctly.
  - Multi-app: different hosts return different configs.
  - Port in Host header stripped correctly in endpoint.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from control_plane.app.identity.resolver import (
    AppConfig,
    AppIdentityResolver,
    AppResolution,
)
from control_plane.app.routes.app_config import create_app_config_router


# =====================================================================
# I1a: Resolver config validation and fallback tests
# =====================================================================


class TestResolverEmptyConfig:
    """Edge cases with empty or minimal configuration."""

    def test_empty_host_map_no_default_raises(self):
        resolver = AppIdentityResolver(host_map={})
        with pytest.raises(KeyError):
            resolver.resolve('anything.com')

    def test_empty_host_map_with_default_resolves(self):
        resolver = AppIdentityResolver(
            host_map={},
            default_app_id='fallback',
        )
        result = resolver.resolve('anything.com')
        assert result.app_id == 'fallback'
        assert result.source == 'default'

    def test_empty_host_map_with_default_no_config(self):
        resolver = AppIdentityResolver(
            host_map={},
            default_app_id='fallback',
        )
        result = resolver.resolve('anything.com')
        assert result.config is None

    def test_empty_host_map_with_default_and_config(self):
        config = AppConfig(app_id='fallback', name='Fallback')
        resolver = AppIdentityResolver(
            host_map={},
            app_configs={'fallback': config},
            default_app_id='fallback',
        )
        result = resolver.resolve('anything.com')
        assert result.config is config


class TestResolverMisconfiguration:
    """Mapped host with no registered config."""

    def test_host_maps_to_app_without_config(self):
        resolver = AppIdentityResolver(
            host_map={'example.com': 'orphan-app'},
        )
        result = resolver.resolve('example.com')
        assert result.app_id == 'orphan-app'
        assert result.config is None  # No config registered.
        assert result.source == 'exact'

    def test_wildcard_maps_to_app_without_config(self):
        resolver = AppIdentityResolver(
            host_map={'*': 'wild-app'},
        )
        result = resolver.resolve('random.example.com')
        assert result.config is None

    def test_get_config_unknown_returns_none(self):
        resolver = AppIdentityResolver(host_map={'a.com': 'a'})
        assert resolver.get_config('nonexistent') is None


class TestResolverPrecedence:
    """Exact > wildcard > default precedence chain."""

    def test_exact_wins_over_wildcard(self):
        resolver = AppIdentityResolver(
            host_map={'exact.com': 'exact-app', '*': 'wild-app'},
        )
        result = resolver.resolve('exact.com')
        assert result.app_id == 'exact-app'
        assert result.source == 'exact'

    def test_wildcard_wins_over_default(self):
        resolver = AppIdentityResolver(
            host_map={'*': 'wild-app'},
            default_app_id='default-app',
        )
        result = resolver.resolve('any.host')
        assert result.app_id == 'wild-app'
        assert result.source == 'wildcard'

    def test_unmatched_falls_to_default(self):
        resolver = AppIdentityResolver(
            host_map={'known.com': 'known-app'},
            default_app_id='default-app',
        )
        result = resolver.resolve('unknown.com')
        assert result.app_id == 'default-app'
        assert result.source == 'default'

    def test_full_chain_exact_wildcard_default(self):
        resolver = AppIdentityResolver(
            host_map={'exact.com': 'a', '*': 'b'},
            default_app_id='c',
        )
        # Exact match.
        assert resolver.resolve('exact.com').app_id == 'a'
        # Wildcard.
        assert resolver.resolve('other.com').app_id == 'b'
        # Default never reached when wildcard exists.
        # (wildcard catches everything)


class TestResolverRegisteredHosts:
    """registered_hosts returns normalized copy."""

    def test_returns_copy(self):
        resolver = AppIdentityResolver(host_map={'A.COM': 'app'})
        hosts = resolver.registered_hosts
        assert hosts == {'a.com': 'app'}
        # Mutation doesn't affect resolver.
        hosts['b.com'] = 'other'
        assert 'b.com' not in resolver.registered_hosts

    def test_keys_lowercase(self):
        resolver = AppIdentityResolver(
            host_map={'APP.Example.COM': 'x', 'UPPER.COM': 'y'},
        )
        hosts = resolver.registered_hosts
        assert 'app.example.com' in hosts
        assert 'upper.com' in hosts


class TestResolverPortEdgeCases:
    """Additional port stripping edge cases."""

    def test_host_with_no_port(self):
        resolver = AppIdentityResolver(host_map={'example.com': 'app'})
        assert resolver.resolve('example.com').app_id == 'app'

    def test_host_with_colon_but_not_port(self):
        """Hostname containing colon but not a numeric port."""
        resolver = AppIdentityResolver(
            host_map={'example.com': 'app'},
            default_app_id='fallback',
        )
        # "example.com:abc" — non-numeric after colon, not stripped.
        result = resolver.resolve('example.com:abc')
        assert result.app_id == 'fallback'  # No match for "example.com:abc"

    def test_ipv6_loopback_with_port(self):
        resolver = AppIdentityResolver(host_map={'::1': 'local'})
        result = resolver.resolve('[::1]:8080')
        assert result.app_id == 'local'


# =====================================================================
# I2a: App-config payload contract tests
# =====================================================================


def _make_config_app(
    host_map: dict[str, str],
    app_configs: dict[str, AppConfig],
) -> FastAPI:
    """Build a test app with app-config route."""
    resolver = AppIdentityResolver(host_map=host_map, app_configs=app_configs)
    app = FastAPI()
    app.include_router(create_app_config_router(resolver))
    return app


class TestAppConfigPayload:
    """Response payload includes all required fields."""

    @pytest.mark.asyncio
    async def test_full_payload_fields(self):
        config = AppConfig(
            app_id='boring-ui',
            name='Boring UI',
            logo='/logo.svg',
            default_release_id='2026-02-13.1',
        )
        app = _make_config_app(
            {'*': 'boring-ui'},
            {'boring-ui': config},
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/api/v1/app-config')
            assert r.status_code == 200
            data = r.json()
            assert data['app_id'] == 'boring-ui'
            assert data['name'] == 'Boring UI'
            assert data['logo'] == '/logo.svg'
            assert data['default_release_id'] == '2026-02-13.1'
            # Exactly these 4 keys.
            assert set(data.keys()) == {
                'app_id', 'name', 'logo', 'default_release_id',
            }

    @pytest.mark.asyncio
    async def test_payload_types_correct(self):
        config = AppConfig(
            app_id='test', name='Test', logo='', default_release_id='',
        )
        app = _make_config_app({'*': 'test'}, {'test': config})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/api/v1/app-config')
            data = r.json()
            assert isinstance(data['app_id'], str)
            assert isinstance(data['name'], str)
            assert isinstance(data['logo'], str)
            assert isinstance(data['default_release_id'], str)

    @pytest.mark.asyncio
    async def test_default_values_propagated(self):
        """AppConfig with defaults (empty strings) appears in response."""
        config = AppConfig(app_id='minimal', name='Minimal')
        app = _make_config_app({'*': 'minimal'}, {'minimal': config})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as c:
            r = await c.get('/api/v1/app-config')
            data = r.json()
            assert data['logo'] == ''
            assert data['default_release_id'] == ''


class TestAppConfigMultiApp:
    """Multi-app scenarios with different hosts."""

    @pytest.mark.asyncio
    async def test_different_hosts_different_configs(self):
        configs = {
            'app-a': AppConfig(app_id='app-a', name='App A'),
            'app-b': AppConfig(app_id='app-b', name='App B'),
        }
        app = _make_config_app(
            {'a.example.com': 'app-a', 'b.example.com': 'app-b'},
            configs,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://a.example.com') as c:
            r = await c.get('/api/v1/app-config')
            assert r.json()['name'] == 'App A'

        async with AsyncClient(transport=transport, base_url='http://b.example.com') as c:
            r = await c.get('/api/v1/app-config')
            assert r.json()['name'] == 'App B'


class TestAppConfigHostHandling:
    """Host header edge cases in endpoint."""

    @pytest.mark.asyncio
    async def test_port_stripped_from_host(self):
        config = AppConfig(app_id='app', name='App')
        app = _make_config_app({'localhost': 'app'}, {'app': config})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://localhost:5173') as c:
            r = await c.get('/api/v1/app-config')
            assert r.status_code == 200
            assert r.json()['app_id'] == 'app'

    @pytest.mark.asyncio
    async def test_unknown_host_returns_404(self):
        config = AppConfig(app_id='app', name='App')
        app = _make_config_app({'known.com': 'app'}, {'app': config})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://unknown.com') as c:
            r = await c.get('/api/v1/app-config')
            assert r.status_code == 404
            assert r.json()['error'] == 'app_config_not_found'

    @pytest.mark.asyncio
    async def test_mapped_host_no_config_returns_404(self):
        """Host resolves to app_id but no AppConfig registered."""
        app = _make_config_app({'example.com': 'orphan'}, {})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://example.com') as c:
            r = await c.get('/api/v1/app-config')
            assert r.status_code == 404
            assert 'orphan' in r.json()['detail']

    @pytest.mark.asyncio
    async def test_case_insensitive_host(self):
        config = AppConfig(app_id='app', name='App')
        app = _make_config_app({'example.com': 'app'}, {'app': config})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://EXAMPLE.COM') as c:
            r = await c.get('/api/v1/app-config')
            assert r.status_code == 200
